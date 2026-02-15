# Casa Teva - Cloudflare Tunnel Setup for Contabo VPS
# Run as Administrator AFTER cloudflared tunnel login
#
# Prerequisites:
#   1. cloudflared installed: winget install Cloudflare.cloudflared
#      OR download from https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
#   2. cloudflared tunnel login  (opens browser, authenticates with Cloudflare)
#   3. Domain fincaradar.com in Cloudflare (already configured)
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File C:\casa-teva\scripts\setup_cloudflare_tunnel.ps1

$ErrorActionPreference = "Stop"

$TUNNEL_NAME = "casa-teva"
$DOMAIN = "fincaradar.com"
$LOCAL_URL = "http://localhost:8000"
$CLOUDFLARED_DIR = "$env:USERPROFILE\.cloudflared"

Write-Host "=============================" -ForegroundColor Cyan
Write-Host "Cloudflare Tunnel Setup" -ForegroundColor Cyan
Write-Host "=============================" -ForegroundColor Cyan

# ---- 1. Verify cloudflared ----
Write-Host "`n[1/5] Checking cloudflared..." -ForegroundColor Yellow
$cf = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cf) {
    Write-Host "  cloudflared not found. Installing via winget..." -ForegroundColor Red
    winget install Cloudflare.cloudflared --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
}
cloudflared --version
Write-Host "  OK" -ForegroundColor Green

# ---- 2. Create tunnel ----
Write-Host "`n[2/5] Creating tunnel '$TUNNEL_NAME'..." -ForegroundColor Yellow
$existing = cloudflared tunnel list 2>&1 | Select-String $TUNNEL_NAME
if ($existing) {
    Write-Host "  Tunnel already exists, skipping create" -ForegroundColor Gray
} else {
    cloudflared tunnel create $TUNNEL_NAME
}

# Get tunnel ID
$tunnelInfo = cloudflared tunnel list 2>&1 | Select-String $TUNNEL_NAME
$tunnelId = ($tunnelInfo -split '\s+')[0]
Write-Host "  Tunnel ID: $tunnelId" -ForegroundColor Gray
Write-Host "  OK" -ForegroundColor Green

# ---- 3. Route DNS ----
Write-Host "`n[3/5] Routing DNS: $DOMAIN -> tunnel..." -ForegroundColor Yellow
cloudflared tunnel route dns $TUNNEL_NAME $DOMAIN 2>&1
Write-Host "  Also routing www.$DOMAIN..." -ForegroundColor Gray
cloudflared tunnel route dns $TUNNEL_NAME "www.$DOMAIN" 2>&1
Write-Host "  OK" -ForegroundColor Green

# ---- 4. Create config ----
Write-Host "`n[4/5] Writing config.yml..." -ForegroundColor Yellow
$configContent = @"
tunnel: $tunnelId
credentials-file: $CLOUDFLARED_DIR\$tunnelId.json

ingress:
  - hostname: $DOMAIN
    service: $LOCAL_URL
    originRequest:
      noTLSVerify: true
  - hostname: www.$DOMAIN
    service: $LOCAL_URL
    originRequest:
      noTLSVerify: true
  - service: http_status:404
"@
$configContent | Out-File -FilePath "$CLOUDFLARED_DIR\config.yml" -Encoding utf8
Write-Host "  Written to $CLOUDFLARED_DIR\config.yml" -ForegroundColor Gray
Write-Host "  OK" -ForegroundColor Green

# ---- 5. NSSM Service ----
Write-Host "`n[5/5] Creating NSSM service: CloudflareTunnel..." -ForegroundColor Yellow
$cloudflaredExe = (Get-Command cloudflared).Source

# Remove if exists (for re-runs)
nssm stop CloudflareTunnel 2>$null
nssm remove CloudflareTunnel confirm 2>$null

nssm install CloudflareTunnel $cloudflaredExe
nssm set CloudflareTunnel AppParameters "tunnel run $TUNNEL_NAME"
nssm set CloudflareTunnel AppDirectory $CLOUDFLARED_DIR
nssm set CloudflareTunnel AppStdout "C:\casa-teva\logs\tunnel.log"
nssm set CloudflareTunnel AppStderr "C:\casa-teva\logs\tunnel-error.log"
nssm set CloudflareTunnel DisplayName "Cloudflare Tunnel - Casa Teva"
nssm set CloudflareTunnel Description "Cloudflare Tunnel: fincaradar.com -> localhost:8000"
nssm set CloudflareTunnel Start SERVICE_AUTO_START
nssm set CloudflareTunnel AppRestartDelay 5000
nssm start CloudflareTunnel
Write-Host "  OK" -ForegroundColor Green

# ---- Summary ----
Write-Host "`n=============================" -ForegroundColor Cyan
Write-Host "Tunnel Setup Complete!" -ForegroundColor Cyan
Write-Host "=============================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Domain:  https://$DOMAIN" -ForegroundColor White
Write-Host "Tunnel:  $TUNNEL_NAME ($tunnelId)" -ForegroundColor Gray
Write-Host "Service: CloudflareTunnel (NSSM)" -ForegroundColor Gray
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Update .env on VPS:" -ForegroundColor Gray
Write-Host "     ALLOWED_HOSTS=localhost,127.0.0.1,$DOMAIN,www.$DOMAIN" -ForegroundColor White
Write-Host "     CSRF_TRUSTED_ORIGINS=https://$DOMAIN,https://www.$DOMAIN" -ForegroundColor White
Write-Host "  2. Restart web: nssm restart CasaTevaWeb" -ForegroundColor Gray
Write-Host "  3. Test: curl https://$DOMAIN/health/" -ForegroundColor Gray
