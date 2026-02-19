# Siguiente Sesion - FincaRadar

> Actualizado: 19 Feb 2026, session 4

## Estado del Sistema: TODO OK

### Scrapers (4/4 operativos, 2 tenants)

| Portal | Donde | Tenant 1 (Cataluna) | Tenant 2 (Madrid) |
|--------|-------|---------------------|-------------------|
| habitaclia | VPS + GH | salou,cambrils,tarragona,reus | chamartin,hortaleza |
| milanuncios | VPS + GH | salou,cambrils,tarragona,reus | chamartin,hortaleza |
| fotocasa | GH Actions | salou,cambrils,tarragona,reus | chamartin,hortaleza |
| idealista | GH Actions | salou,cambrils,tarragona,reus | chamartin,hortaleza |

### Workflows

| Workflow | Cron | Tenant | Portales |
|----------|------|--------|----------|
| `scrape-neon.yml` | L-X-V 12:00 UTC | 1 (Casa Teva) | fotocasa, idealista, habitaclia, milanuncios |
| `scrape-madrid.yml` | L-X-V 12:30 UTC | 2 (Find&Look) | fotocasa, idealista |
| VPS `scheduled_scrape.py` | L-X-V 13:00 CET | 1+2 | habitaclia, milanuncios (ambos tenants) |
| `contact-queue.yml` | L-V 18:00 UTC | todos | procesamiento cola contactos |

### Infraestructura

- **Web**: fincaradar.com (Cloudflare Tunnel -> VPS waitress:8000)
- **DB**: Neon PostgreSQL (serverless)
- **Health**: `/status/scrapers/` - dashboard green/yellow/red
- **Monitoring**: error_handling.py -> Telegram alerts (4 scrapers)
- **PWA**: manifest.json, favicon, icons, service-worker
- **Brand**: FincaRadar
- **Tenants**: Casa Teva (id=1), Find&Look (id=2)

---

## Completado Session 4 (19 Feb 2026)

- [x] VPS deploy (git pull + nssm restart)
- [x] Tenant Find&Look creado en BD (id=2, user: mariano)
- [x] Health check OK
- [x] Auditoria 18 paginas: todas OK (200)
- [x] Bug fix: `fecha_primer_contacto` ambigua en analytics KPIs
- [x] Bug fix: `scraped_at` -> `scraping_timestamp` en scrape_history y zones_grid
- [x] Bug fix: `core_zonageografica` -> `zonas_geograficas` en zones_grid
- [x] Bug fix: `leads_contactqueue` -> `leads_contact_queue` en system_status y scraper_health
- [x] Bug fix: widget service INSERT con columnas correctas (raw_data, scraping_timestamp)

### UI ya implementada (no estaba en NEXT_SESSION anterior)

- Contactos (`/leads/contacts/`) - lista, detalle, interacciones, notas
- Cola de Contactos (`/leads/contact-queue/`) - filtros, cancelar, reintentar, marcar respondido
- Calendario (`/leads/calendar/`)
- Agenda (`/leads/agenda/`)
- Analytics completo (`/analytics/dashboard/`) - KPIs, embudo, charts, filtros
- Real-Time dashboard (`/analytics/realtime/`)
- Mapa (`/analytics/mapa/`)
- Scrape History (`/analytics/scrapes/`)
- Zones Grid (`/analytics/zonas/`)
- ACM valoracion (`/analytics/valoracion/`)
- API Docs (`/api/docs/`) - Swagger/OpenAPI

---

## Pendiente

### Necesita accion manual del usuario
- [ ] Deploy VPS con bug fixes de session 4
- [ ] Cambiar password "changeme" de Mariano (Find&Look)
- [ ] Regenerar GH_TOKEN en VPS (expuesto en terminal session 2)
- [ ] Credenciales portales Find&Look (si tiene cuentas propias)
- [ ] Datos comerciales Find&Look (nombre, email, telefono para templates)

### Desarrollo pendiente
- [ ] Quick-scan alternativo con Camoufox (si se necesita frecuencia alta)
- [ ] WhatsApp Business API (Issue #32)
- [ ] Ollama image scoring en produccion (PoC done, Issue #36)
- [ ] Rate limiting scrapers (Issue #28 ALTO)

### Nice-to-have
- [ ] Redis cache
- [ ] Load testing
- [ ] Application Insights / APM

---

## Deploy VPS (bug fixes session 4)

```bash
ssh vps "cd C:\casa-teva; git pull; cd C:\casa-teva\backend; C:\casa-teva\venv\Scripts\python.exe manage.py collectstatic --noinput; nssm restart CasaTevaWeb"
```

---

## Decisiones pendientes (Find&Look)

1. **Password para Mariano**: cambiar default "changeme"
2. **Credenciales portales**: Tiene cuentas propias? O usa las de Casa Teva?
3. **Datos comerciales**: nombre, email, telefono para template de mensajes
4. **Rango de precios**: filtrar por min/max? (ahora 50k-1M EUR)
5. **Solo particulares**: O tambien profesionales? (ahora: solo particulares)

---

## Comandos utiles

```bash
# Deploy a VPS
ssh vps "cd C:\casa-teva; git pull; cd C:\casa-teva\backend; C:\casa-teva\venv\Scripts\python.exe manage.py collectstatic --noinput; nssm restart CasaTevaWeb"

# Health
ssh vps "curl.exe -s http://localhost:8000/health/"
ssh vps "curl.exe -s http://localhost:8000/status/scrapers/"

# Scraping manual Madrid
gh workflow run scrape-madrid.yml -f portals="fotocasa,idealista" -f zones="chamartin,hortaleza"

# Scraping manual principal
gh workflow run scrape-neon.yml -f portals="fotocasa,idealista" -f zones="salou"

# GH Actions runs
gh run list --workflow=scrape-madrid.yml --limit=3
gh run list --workflow=scrape-neon.yml --limit=3
```
