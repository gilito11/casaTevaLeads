# Dockerfile para Casa Teva Lead System
# Multi-stage build para optimizar tamaño

# Stage 1: Base con Python y dependencias del sistema
FROM python:3.11-slim as base

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root
RUN useradd -m -u 1000 casateva

# Stage 2: Builder - instalar dependencias Python
FROM base as builder

WORKDIR /app

# Copiar requirements
COPY requirements.txt requirements-dev.txt ./

# Instalar dependencias en un virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 3: Runtime - imagen final
FROM base as runtime

# Instalar dependencias de Playwright, Botasaurus y Camoufox
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    wget \
    gnupg \
    # Camoufox dependencies (Firefox-based anti-detect browser)
    xvfb \
    libgtk-3-0 \
    libdbus-glib-1-2 \
    && rm -rf /var/lib/apt/lists/*

# Instalar Google Chrome para Botasaurus
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Copiar virtual environment desde builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Instalar navegadores de Playwright en directorio compartido
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN mkdir -p /opt/playwright && \
    playwright install chromium && \
    chmod -R 755 /opt/playwright

# Crear directorios
WORKDIR /app
RUN mkdir -p /app/backend /app/dagster /app/dbt_project /app/scrapers

# Crear directorios para Dagster con permisos correctos
RUN mkdir -p /tmp/dagster /opt/dagster/dagster_home && \
    chown -R casateva:casateva /tmp/dagster /opt/dagster

# Crear directorios para Botasaurus (error_logs, output, profiles)
# Botasaurus requiere estos directorios con permisos de escritura
RUN mkdir -p /app/error_logs /app/output /app/profiles && \
    chown -R casateva:casateva /app/error_logs /app/output /app/profiles

# Crear directorio .cache para Camoufox con permisos de casateva
# Camoufox guarda el browser en ~/.cache/camoufox/
RUN mkdir -p /home/casateva/.cache && \
    chown -R casateva:casateva /home/casateva

# Copiar código de la aplicación
COPY --chown=casateva:casateva backend/ /app/backend/
COPY --chown=casateva:casateva dagster/ /app/dagster/
COPY --chown=casateva:casateva dbt_project/ /app/dbt_project/
COPY --chown=casateva:casateva scrapers/ /app/scrapers/
COPY --chown=casateva:casateva scripts/ /app/scripts/
COPY --chown=casateva:casateva run_*_scraper.py /app/
COPY --chown=casateva:casateva run_all_scrapers.py /app/
COPY --chown=casateva:casateva scrapy.cfg /app/

# Cambiar a usuario no-root
USER casateva

# Descargar browser de Camoufox como usuario casateva
# (IMPORTANTE: debe ejecutarse como casateva para que guarde en ~/.cache/camoufox/)
RUN camoufox fetch

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DJANGO_SETTINGS_MODULE=casa_teva.settings
ENV DAGSTER_HOME=/opt/dagster/dagster_home
ENV TMPDIR=/tmp/dagster

# Exponer puertos
EXPOSE 8000 3000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Comando por defecto (puede ser override en docker-compose)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--chdir", "/app/backend", "casa_teva.wsgi:application"]
