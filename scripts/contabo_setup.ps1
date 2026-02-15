# Casa Teva Lead System - Contabo VPS Setup Script
# Run this on the VPS (Windows Server 2022) as Administrator
#
# Prerequisites:
#   - Python 3.13+ installed at C:\Python313\
#   - Git installed
#   - Google Chrome installed
#   - NSSM installed (https://nssm.cc/)
#   - Repo cloned to C:\casa-teva\
#   - .env configured at C:\casa-teva\.env
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File C:\casa-teva\scripts\contabo_setup.ps1

$ErrorActionPreference = "Stop"
$PROJECT = "C:\casa-teva"
$PYTHON_SYS = "C:\Python313\python.exe"
$PYTHON = "$PROJECT\venv\Scripts\python.exe"
$LOGS = "$PROJECT\logs"

Write-Host "=============================" -ForegroundColor Cyan
Write-Host "Casa Teva VPS Setup" -ForegroundColor Cyan
Write-Host "=============================" -ForegroundColor Cyan

# ---- 1. Create directories ----
Write-Host "`n[1/7] Creating directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $LOGS | Out-Null
New-Item -ItemType Directory -Force -Path "$PROJECT\output" | Out-Null
New-Item -ItemType Directory -Force -Path "$PROJECT\error_logs" | Out-Null
New-Item -ItemType Directory -Force -Path "$PROJECT\profiles" | Out-Null
Write-Host "  OK" -ForegroundColor Green

# ---- 2. Virtual environment ----
Write-Host "`n[2/7] Setting up Python venv..." -ForegroundColor Yellow
if (-not (Test-Path "$PROJECT\venv")) {
    & $PYTHON_SYS -m venv "$PROJECT\venv"
}
& $PYTHON -m pip install --upgrade pip
& $PYTHON -m pip install -r "$PROJECT\requirements.txt"
Write-Host "  OK" -ForegroundColor Green

# ---- 3. Install browsers ----
Write-Host "`n[3/7] Installing browsers..." -ForegroundColor Yellow
& "$PROJECT\venv\Scripts\camoufox.exe" fetch
& $PYTHON -m playwright install chromium
Write-Host "  OK" -ForegroundColor Green

# ---- 4. Django setup ----
Write-Host "`n[4/7] Django collectstatic + migrate..." -ForegroundColor Yellow
Push-Location "$PROJECT\backend"
& $PYTHON manage.py collectstatic --noinput
& $PYTHON manage.py migrate --noinput
Pop-Location
Write-Host "  OK" -ForegroundColor Green

# ---- 5. NSSM: Django Web Service ----
Write-Host "`n[5/7] Configuring NSSM service: CasaTevaWeb..." -ForegroundColor Yellow
nssm install CasaTevaWeb $PYTHON
nssm set CasaTevaWeb AppParameters "$PROJECT\scripts\start_web.py"
nssm set CasaTevaWeb AppDirectory $PROJECT
nssm set CasaTevaWeb AppStdout "$LOGS\web.log"
nssm set CasaTevaWeb AppStderr "$LOGS\web-error.log"
nssm set CasaTevaWeb AppRotateFiles 1
nssm set CasaTevaWeb AppRotateBytes 10485760
nssm set CasaTevaWeb DisplayName "Casa Teva CRM Web"
nssm set CasaTevaWeb Description "Django CRM served via waitress on port 8000"
nssm set CasaTevaWeb Start SERVICE_AUTO_START
nssm set CasaTevaWeb AppRestartDelay 5000
nssm start CasaTevaWeb
Write-Host "  OK - http://localhost:8000/health/" -ForegroundColor Green

# ---- 6. Scheduled Tasks ----
Write-Host "`n[6/7] Creating Windows Scheduled Tasks..." -ForegroundColor Yellow

# VPS scrape (habitaclia + milanuncios only): L-X-V 13:00 CET
# fotocasa + idealista stay on GitHub Actions (blocked by Imperva/DataDome)
schtasks /Create /SC WEEKLY /D MON,WED,FRI /ST 13:00 `
    /TN "CasaTeva\FullScrape" `
    /TR "$PYTHON $PROJECT\scripts\scheduled_scrape.py" /F
Write-Host "  FullScrape: hab+mil (L-X-V 13:00)" -ForegroundColor Gray

# Contact queue: L-V 18:00 CET (17:00 UTC)
schtasks /Create /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 18:00 `
    /TN "CasaTeva\ContactQueue" `
    /TR "$PYTHON $PROJECT\scripts\scheduled_contact.py" /F
Write-Host "  ContactQueue (L-V 18:00)" -ForegroundColor Gray
Write-Host "  OK" -ForegroundColor Green

# ---- 7. Summary ----
Write-Host "`n=============================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Cyan
Write-Host "=============================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services:" -ForegroundColor White
Write-Host "  CasaTevaWeb    -> http://localhost:8000/health/" -ForegroundColor Gray
Write-Host ""
Write-Host "Scheduled Tasks:" -ForegroundColor White
Write-Host "  FullScrape     -> L-X-V 13:00 CET (hab+mil only)" -ForegroundColor Gray
Write-Host "  ContactQueue   -> L-V 18:00 CET" -ForegroundColor Gray
Write-Host ""
Write-Host "Logs: $LOGS" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Test: curl http://localhost:8000/health/" -ForegroundColor Gray
Write-Host "  2. Setup Cloudflare Tunnel (see below)" -ForegroundColor Gray
Write-Host "  3. Run a manual scrape: $PYTHON $PROJECT\scripts\scheduled_scrape.py" -ForegroundColor Gray
Write-Host ""
Write-Host "Cloudflare Tunnel setup:" -ForegroundColor Yellow
Write-Host "  1. Download cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/" -ForegroundColor Gray
Write-Host "  2. cloudflared tunnel login" -ForegroundColor Gray
Write-Host "  3. cloudflared tunnel create casa-teva" -ForegroundColor Gray
Write-Host "  4. cloudflared tunnel route dns casa-teva <your-domain>" -ForegroundColor Gray
Write-Host "  5. Create C:\cloudflared\config.yml (see plan)" -ForegroundColor Gray
Write-Host "  6. nssm install CloudflareTunnel C:\cloudflared\cloudflared.exe" -ForegroundColor Gray
Write-Host "     nssm set CloudflareTunnel AppParameters 'tunnel run casa-teva'" -ForegroundColor Gray
Write-Host "     nssm start CloudflareTunnel" -ForegroundColor Gray
