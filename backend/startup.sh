#!/bin/bash

# Azure App Service startup script for Django

# Navigate to project root
cd /home/site/wwwroot

# Install Playwright browsers if not already installed
# Use /home directory which persists across restarts
export PLAYWRIGHT_BROWSERS_PATH=/home/playwright
if [ ! -d "$PLAYWRIGHT_BROWSERS_PATH/chromium-"* ]; then
    echo "Installing Playwright browsers..."
    python -m playwright install chromium
    echo "Playwright browsers installed."
else
    echo "Playwright browsers already installed."
fi

# Navigate to backend directory
cd /home/site/wwwroot/backend

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate --noinput

# Start gunicorn
gunicorn casa_teva.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 600
