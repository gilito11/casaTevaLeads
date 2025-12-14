#!/bin/bash

# Azure App Service startup script for Django

# Navigate to backend directory
cd /home/site/wwwroot/backend

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate --noinput

# Start gunicorn
gunicorn casa_teva.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 600
