# Runbooks de Operacion - Casa Teva

Procedimientos para resolver incidentes comunes en produccion.

---

## 1. Scraper no produce resultados

**Sintomas**: 0 leads nuevos, alerta Discord "No listings found"

**Diagnostico**:
```bash
# Ver logs del scraper
az containerapp logs show -n dagster-scrapers -g inmoleads-crm --type console --tail 100

# Verificar datos en BD
psql -h inmoleads-db.postgres.database.azure.com -U inmoleadsadmin -d inmoleadsdb -c \
  "SELECT portal, COUNT(*) FROM raw.raw_listings WHERE fecha_scraping > NOW() - INTERVAL '24 hours' GROUP BY portal"
```

**Causas posibles**:
1. Portal bloqueando requests -> Aumentar `request_delay`
2. Cambio de estructura HTML -> Actualizar selectores
3. Error de red/API -> Verificar ScrapingBee dashboard
4. Zona sin anuncios -> Verificar manualmente el portal

**Solucion**:
1. Si bloqueo: Esperar 1-2 horas, ScrapingBee rota IPs
2. Si HTML cambiado: Actualizar scraper y deploy
3. Si API error: Contactar ScrapingBee soporte

---

## 2. Cambio de estructura HTML detectado

**Sintomas**: Alerta ">50% anuncios sin datos basicos"

**Diagnostico**:
```bash
# Ver metricas de scraping
psql -h inmoleads-db.postgres.database.azure.com -U inmoleadsadmin -d inmoleadsdb -c \
  "SELECT portal,
          COUNT(*) as total,
          SUM(CASE WHEN raw_data->>'titulo' IS NULL THEN 1 ELSE 0 END) as sin_titulo,
          SUM(CASE WHEN raw_data->>'precio' IS NULL THEN 1 ELSE 0 END) as sin_precio
   FROM raw.raw_listings
   WHERE fecha_scraping > NOW() - INTERVAL '6 hours'
   GROUP BY portal"
```

**Solucion**:
1. Acceder manualmente al portal afectado
2. Inspeccionar HTML con DevTools
3. Actualizar selectores en `scrapers/botasaurus_*.py` o `scrapers/scrapingbee_*.py`
4. Testear localmente: `python run_*_scraper.py --zones salou --max-pages 1`
5. Commit y push para deploy automatico

---

## 3. Base de datos llena o lenta

**Sintomas**: Timeouts, errores de conexion

**Diagnostico**:
```bash
# Verificar uso de disco
az postgres flexible-server show --name inmoleads-db --resource-group inmoleads-crm \
  --query "{storage:storage.storageSizeGb, tier:sku.tier}"

# Verificar conexiones activas
psql -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
```

**Solucion**:
1. Limpiar datos antiguos (>90 dias):
   ```sql
   DELETE FROM raw.raw_listings WHERE fecha_scraping < NOW() - INTERVAL '90 days';
   VACUUM ANALYZE raw.raw_listings;
   ```
2. Aumentar almacenamiento en Azure Portal
3. Verificar queries lentas en Query Performance Insight

---

## 4. API timeout / 503 errors

**Sintomas**: CRM lento o no responde

**Diagnostico**:
```bash
# Health check
curl https://inmoleads-crm.azurewebsites.net/health/

# Ver logs Web App
az webapp log tail --name inmoleads-crm --resource-group inmoleads-crm
```

**Causas posibles**:
1. BD no responde -> Ver runbook #3
2. Web App sin recursos -> Escalar en Azure Portal
3. Deploy fallido -> Rollback a revision anterior

**Solucion**:
1. Si BD: Reiniciar PostgreSQL desde Azure Portal
2. Si recursos: `az webapp scale --name inmoleads-crm -g inmoleads-crm --instance-count 2`
3. Si deploy: `az webapp deployment slot swap -n inmoleads-crm -g inmoleads-crm --slot staging`

---

## 5. ScrapingBee sin creditos

**Sintomas**: Error 402 en logs, alertas de fallos

**Diagnostico**:
- Dashboard: https://app.scrapingbee.com/
- Ver uso en "Usage" section

**Solucion**:
1. Reducir frecuencia de scraping temporalmente
2. Usar solo Botasaurus (habitaclia, fotocasa) hasta renovacion
3. Contactar ScrapingBee para upgrade si es recurrente

---

## 6. Dagster schedule no ejecuta

**Sintomas**: No hay runs nuevos en la UI de Dagster

**Diagnostico**:
```bash
# Verificar estado del container
az containerapp show -n dagster-scrapers -g inmoleads-crm --query "properties.runningStatus"

# Ver logs
az containerapp logs show -n dagster-scrapers -g inmoleads-crm --type console --tail 200
```

**Solucion**:
1. Verificar schedule activo en Dagster UI -> Schedules
2. Reiniciar container:
   ```bash
   az containerapp revision restart -n dagster-scrapers -g inmoleads-crm \
     --revision $(az containerapp revision list -n dagster-scrapers -g inmoleads-crm --query "[0].name" -o tsv)
   ```
3. Verificar PostgreSQL storage de Dagster

---

## Contactos de Escalacion

| Nivel | Contacto | Tiempo respuesta |
|-------|----------|------------------|
| L1 | Alertas Discord | Automatico |
| L2 | Admin sistema | 1h horario laboral |
| L3 | Azure Support | Segun SLA |

## Historial de Incidentes

| Fecha | Incidente | Causa | Resolucion |
|-------|-----------|-------|------------|
| - | - | - | - |
