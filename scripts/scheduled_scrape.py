#!/usr/bin/env python3
"""VPS scraping scheduled task - runs ALL 4 portals via Scrapling.

Schedule: L-X-V 13:00 CET (12:00 UTC) via Windows Task Scheduler.

Scrapling (Patchright) bypasses DataDome (idealista) and Imperva (fotocasa,
habitaclia) without a proxy, so all 4 portals can now run on the VPS.
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

# dbt (profiles.yml) lee DBT_HOST/USER/PASSWORD/DBNAME. El .env del VPS solo
# trae DATABASE_URL, así que derivamos las DBT_* de ahí si no están -> el canal
# dbt del VPS deja de irse a localhost.
def _ensure_dbt_env():
    from urllib.parse import urlparse
    if os.environ.get('DBT_HOST'):
        return
    url = os.environ.get('DATABASE_URL') or os.environ.get('NEON_DATABASE_URL', '')
    if not url:
        return
    p = urlparse(url)
    os.environ['DBT_HOST'] = p.hostname or ''
    os.environ['DBT_USER'] = p.username or ''
    os.environ['DBT_PASSWORD'] = p.password or ''
    os.environ['DBT_DBNAME'] = (p.path or '').lstrip('/').split('?')[0]

_ensure_dbt_env()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

PYTHON = os.path.join(PROJECT_ROOT, 'venv', 'Scripts', 'python.exe')
DBT_EXE = os.path.join(PROJECT_ROOT, 'venv', 'Scripts', 'dbt.exe')
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
DBT_DIR = os.path.join(PROJECT_ROOT, 'dbt_project')
ZONES = os.environ.get('SCRAPE_ZONES', 'salou cambrils tarragona reus').split()

# Tenant 2: Look and Find (Madrid)
MADRID_ZONES = os.environ.get('SCRAPE_ZONES_MADRID', 'chamartin hortaleza').split()
MADRID_TENANT_ID = 2

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


def run_step(desc, cmd, allow_fail=False, timeout=1800, healable=False):
    """Run a subprocess step, log output, return success.

    healable=True: si falla y AUTO_HEAL está activo, invoca Claude Code para
    intentar arreglar el código (causa raíz), y reintenta el paso UNA vez.
    """
    logger.info(f"{'='*60}")
    logger.info(f"STEP: {desc}")
    logger.info(f"CMD: {' '.join(cmd)}")
    logger.info(f"{'='*60}")

    log_file = os.path.join(LOG_DIR, f"scrape_{datetime.date.today()}.log")

    def _run_once():
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                env={**os.environ, 'PYTHONUNBUFFERED': '1'},
            )
        except subprocess.TimeoutExpired:
            return None
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*60}\n{desc} [{datetime.datetime.now()}]\n{'='*60}\n")
            f.write(r.stdout or '')
            if r.stderr:
                f.write(f"\n--- STDERR ---\n{r.stderr}")
        return r

    result = _run_once()
    if result is None:
        logger.error(f"TIMEOUT ({timeout}s): {desc}")
        notify_telegram(f"TIMEOUT: {desc}")
        return False

    if result.returncode == 0:
        logger.info(f"OK: {desc}")
        return True

    logger.warning(f"FAILED (rc={result.returncode}): {desc}")

    # --- Auto-reparación (opt-in) ---
    if healable:
        try:
            from auto_heal import heal, is_enabled
        except Exception:
            try:
                from scripts.auto_heal import heal, is_enabled
            except Exception:
                heal = None
        if heal and is_enabled():
            err_log = ((result.stdout or '') + "\n" + (result.stderr or ''))
            logger.info(f"AUTO_HEAL: intentando reparar '{desc}' con Claude...")
            notify_telegram(f"🛠️ AUTO_HEAL intentando reparar: {desc}")
            attempted, summary = heal(desc, err_log, PROJECT_ROOT)
            if attempted:
                notify_telegram(f"🛠️ AUTO_HEAL {desc}:\n{summary[:600]}")
                # Reintento único con el código ya potencialmente arreglado
                retry = _run_once()
                if retry is not None and retry.returncode == 0:
                    logger.info(f"OK tras auto-heal: {desc}")
                    notify_telegram(f"✅ Reparado y reejecutado OK: {desc}")
                    return True
                logger.warning(f"Sigue fallando tras auto-heal: {desc}")

    if not allow_fail:
        notify_telegram(f"ERROR: {desc}\n{(result.stderr or '')[:500]}")
    return False


def main():
    start = datetime.datetime.now()
    logger.info(f"Full scrape started at {start}")
    logger.info(f"Zones: {ZONES}")

    results = {}

    # 1a. Scrapers Tenant 1 (Casa Teva - Catalonia)
    results['habitaclia'] = run_step(
        "Habitaclia (Catalonia)",
        [PYTHON, "-m", "scrapers.scrapling_habitaclia", "--zones"] + ZONES + ["--postgres"],
        allow_fail=True,
    )
    results['fotocasa'] = run_step(
        "Fotocasa (Catalonia)",
        [PYTHON, "-m", "scrapers.scrapling_fotocasa", "--zones"] + ZONES + ["--postgres"],
        allow_fail=True,
    )
    results['idealista'] = run_step(
        "Idealista (Catalonia)",
        [PYTHON, "-m", "scrapers.scrapling_idealista", "--zones"] + ZONES + ["--max-pages", "2", "--postgres"],
        allow_fail=True,
    )
    results['milanuncios'] = run_step(
        "Milanuncios (Catalonia)",
        [PYTHON, "-m", "scrapers.scrapling_milanuncios", "--zones"] + ZONES + ["--max-pages", "2", "--postgres"],
        allow_fail=True,
    )
    results['wallapop'] = run_step(
        "Wallapop (Catalonia)",
        [PYTHON, "-m", "scrapers.scrapling_wallapop", "--zones"] + ZONES + ["--max-pages", "2", "--postgres"],
        allow_fail=True,
    )

    # 1b. Scrapers Tenant 2 (Look and Find - Madrid)
    results['habitaclia_madrid'] = run_step(
        "Habitaclia (Madrid)",
        [PYTHON, "-m", "scrapers.scrapling_habitaclia", "--zones"] + MADRID_ZONES + ["--tenant-id", str(MADRID_TENANT_ID), "--postgres"],
        allow_fail=True,
    )
    results['fotocasa_madrid'] = run_step(
        "Fotocasa (Madrid)",
        [PYTHON, "-m", "scrapers.scrapling_fotocasa", "--zones"] + MADRID_ZONES + ["--tenant-id", str(MADRID_TENANT_ID), "--postgres"],
        allow_fail=True,
    )
    results['idealista_madrid'] = run_step(
        "Idealista (Madrid)",
        [PYTHON, "-m", "scrapers.scrapling_idealista", "--zones"] + MADRID_ZONES + ["--tenant-id", str(MADRID_TENANT_ID), "--max-pages", "2", "--postgres"],
        allow_fail=True,
    )
    results['milanuncios_madrid'] = run_step(
        "Milanuncios (Madrid)",
        [PYTHON, "-m", "scrapers.scrapling_milanuncios", "--zones"] + MADRID_ZONES + ["--tenant-id", str(MADRID_TENANT_ID), "--max-pages", "2", "--postgres"],
        allow_fail=True,
    )
    results['wallapop_madrid'] = run_step(
        "Wallapop (Madrid)",
        [PYTHON, "-m", "scrapers.scrapling_wallapop", "--zones"] + MADRID_ZONES + ["--tenant-id", str(MADRID_TENANT_ID), "--max-pages", "2", "--postgres"],
        allow_fail=True,
    )

    # 2. dbt transformations
    results['dbt_staging'] = run_step(
        "dbt staging",
        [DBT_EXE, "run", "--select", "staging",
         "--project-dir", DBT_DIR, "--profiles-dir", DBT_DIR],
        healable=True,
    )
    results['dbt_marts'] = run_step(
        "dbt marts",
        [DBT_EXE, "run", "--select", "marts",
         "--project-dir", DBT_DIR, "--profiles-dir", DBT_DIR],
        healable=True,
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
