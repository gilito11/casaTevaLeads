#!/usr/bin/env python3
"""Contact queue scheduled task - replaces GitHub Actions contact-queue.yml cron.

Schedule: L-V 18:00 CET (17:00 UTC) via Windows Task Scheduler.

Processes the contact queue: sends messages to leads via portal forms.
"""
import os
import sys
import subprocess
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


def main():
    logger.info("Processing contact queue...")
    result = subprocess.run(
        [PYTHON, os.path.join("scripts", "process_contact_queue.py")],
        capture_output=True, text=True, timeout=1800,
        env={**os.environ, 'PYTHONUNBUFFERED': '1'},
    )

    if result.returncode != 0:
        logger.error(f"Contact queue failed (rc={result.returncode})")
        logger.error(result.stderr[:1000])
    else:
        logger.info("Contact queue completed successfully")
        if result.stdout:
            logger.info(result.stdout[-500:])


if __name__ == '__main__':
    main()
