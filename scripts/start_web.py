#!/usr/bin/env python3
"""Start Django with waitress WSGI server (Windows-compatible).

Usage:
    python scripts/start_web.py

For NSSM service:
    nssm install CasaTevaWeb "E:\casa-teva\venv\Scripts\python.exe"
    nssm set CasaTevaWeb AppParameters "E:\casa-teva\scripts\start_web.py"
"""
import os
import sys

# Determine project root (parent of scripts/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(PROJECT_ROOT, 'backend')

# Load .env before anything else
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

os.chdir(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'casa_teva.settings')

from waitress import serve
from casa_teva.wsgi import application

HOST = os.environ.get('WAITRESS_HOST', '127.0.0.1')
PORT = int(os.environ.get('PORT', '8000'))
THREADS = int(os.environ.get('WAITRESS_THREADS', '4'))

print(f"Starting waitress on {HOST}:{PORT} (threads={THREADS})")
serve(application, host=HOST, port=PORT, threads=THREADS)
