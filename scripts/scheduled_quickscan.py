#!/usr/bin/env python3
"""Quick scan scheduled task for VPS.

Schedule: L-S cada 2h (09:00-19:00 CET) via Windows Task Scheduler.

Runs habitaclia + milanuncios (page 1 only) + dbt for fast new-lead detection.
fotocasa is blocked on VPS (Imperva) → only on GitHub Actions.
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


def run_step(desc, cmd, timeout=900):
    """Run subprocess, return success."""
    logger.info(f"[QuickScan] {desc}")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, 'PYTHONUNBUFFERED': '1'},
        )
        if result.returncode != 0:
            logger.warning(f"FAILED: {desc} (rc={result.returncode})")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        logger.error(f"TIMEOUT: {desc}")
        return False


def main():
    start = datetime.datetime.now()
    logger.info(f"Quick scan started at {start}, zones: {ZONES}")

    # Only portals that work from VPS (fotocasa blocked by Imperva)
    run_step("Habitaclia",
             [PYTHON, "run_habitaclia_scraper.py", "--zones"] + ZONES + ["--postgres"])
    run_step("Milanuncios",
             [PYTHON, "run_camoufox_milanuncios_scraper.py", "--zones"] + ZONES + ["--max-pages", "1", "--postgres"])

    # dbt: staging + marts
    run_step("dbt",
             [PYTHON, "-m", "dbt", "run", "--select", "staging", "marts",
              "--project-dir", DBT_DIR, "--profiles-dir", DBT_DIR])

    elapsed = datetime.datetime.now() - start
    logger.info(f"Quick scan done in {elapsed.seconds}s")


if __name__ == '__main__':
    main()
