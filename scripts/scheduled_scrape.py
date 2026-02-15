#!/usr/bin/env python3
"""VPS scraping scheduled task - runs portals that work from Contabo.

Schedule: L-X-V 13:00 CET (12:00 UTC) via Windows Task Scheduler.

Runs habitaclia + milanuncios + dbt + auto-queue with Telegram alerts.
fotocasa + idealista are blocked on VPS (Imperva/DataDome) → stay on GitHub Actions.
"""
import os
import sys
import subprocess
import datetime
import logging

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

PYTHON = os.path.join(PROJECT_ROOT, 'venv', 'Scripts', 'python.exe')
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
DBT_DIR = os.path.join(PROJECT_ROOT, 'dbt_project')
ZONES = os.environ.get('SCRAPE_ZONES', 'salou cambrils tarragona reus').split()

os.makedirs(LOG_DIR, exist_ok=True)


def notify_telegram(msg):
    """Send Telegram alert."""
    import requests
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg},
            timeout=10,
        )
    except Exception as e:
        logger.warning(f"Telegram alert failed: {e}")


def run_step(desc, cmd, allow_fail=False, timeout=1800):
    """Run a subprocess step, log output, return success."""
    logger.info(f"{'='*60}")
    logger.info(f"STEP: {desc}")
    logger.info(f"CMD: {' '.join(cmd)}")
    logger.info(f"{'='*60}")

    log_file = os.path.join(LOG_DIR, f"scrape_{datetime.date.today()}.log")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, 'PYTHONUNBUFFERED': '1'},
        )
    except subprocess.TimeoutExpired:
        msg = f"TIMEOUT ({timeout}s): {desc}"
        logger.error(msg)
        notify_telegram(f"TIMEOUT: {desc}")
        return False

    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"\n{'='*60}\n{desc} [{datetime.datetime.now()}]\n{'='*60}\n")
        f.write(result.stdout)
        if result.stderr:
            f.write(f"\n--- STDERR ---\n{result.stderr}")

    if result.returncode != 0:
        logger.warning(f"FAILED (rc={result.returncode}): {desc}")
        if not allow_fail:
            notify_telegram(f"ERROR: {desc}\n{result.stderr[:500]}")
        return False

    logger.info(f"OK: {desc}")
    return True


def main():
    start = datetime.datetime.now()
    logger.info(f"Full scrape started at {start}")
    logger.info(f"Zones: {ZONES}")

    results = {}

    # 1. Scrapers (only portals that work from VPS)
    # fotocasa (Imperva) and idealista (DataDome) are blocked → GitHub Actions only
    results['habitaclia'] = run_step(
        "Habitaclia",
        [PYTHON, "run_habitaclia_scraper.py", "--zones"] + ZONES + ["--postgres"],
    )
    results['milanuncios'] = run_step(
        "Milanuncios",
        [PYTHON, "run_camoufox_milanuncios_scraper.py", "--zones"] + ZONES + ["--max-pages", "2", "--postgres"],
        allow_fail=True,
    )

    # 2. dbt transformations
    results['dbt_staging'] = run_step(
        "dbt staging",
        [PYTHON, "-m", "dbt", "run", "--select", "staging",
         "--project-dir", DBT_DIR, "--profiles-dir", DBT_DIR],
    )
    results['dbt_marts'] = run_step(
        "dbt marts",
        [PYTHON, "-m", "dbt", "run", "--select", "marts",
         "--project-dir", DBT_DIR, "--profiles-dir", DBT_DIR],
    )

    # 3. Auto-queue new leads for contact
    results['auto_queue'] = run_step(
        "Auto-queue",
        [PYTHON, os.path.join("scripts", "post_scrape_auto_queue.py")],
        allow_fail=True,
    )

    elapsed = datetime.datetime.now() - start
    ok = sum(1 for v in results.values() if v)
    total = len(results)

    summary = f"Scrape {datetime.date.today()}: {ok}/{total} OK ({elapsed.seconds // 60}m{elapsed.seconds % 60}s)"
    logger.info(summary)
    notify_telegram(summary)


if __name__ == '__main__':
    main()
