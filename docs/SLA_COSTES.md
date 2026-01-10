# SLA y Costes - Casa Teva Lead System

## Costes Operativos

| Servicio | Coste Mensual | Notas |
|----------|---------------|-------|
| Azure Container Apps (Dagster) | ~20 EUR | Orquestacion de scrapers |
| Azure Web App (CRM) | ~10 EUR | Django + HTMX |
| Azure PostgreSQL | ~30 EUR | PostgreSQL 16, almacenamiento persistente |
| ScrapingBee API | 50 EUR | 250,000 credits/mes |

**Total estimado: ~110 EUR/mes**

### Consumo ScrapingBee

- **Milanuncios**: 75 credits/request (stealth proxy GeeTest)
- **Idealista**: 75 credits/request (stealth proxy DataDome)
- **Habitaclia/Fotocasa**: 0 credits (Botasaurus, gratis)
- **Capacidad**: ~3,333 requests/mes con stealth proxy

## SLA (Service Level Agreement)

| Metrica | Compromiso |
|---------|------------|
| Disponibilidad | 99% (Azure SLA) |
| Frecuencia scraping | 2x dia (12:00 y 18:00 hora Espana) |
| Retencion de datos | Indefinida |
| Soporte | Email en horario laboral |
| Alertas | Discord en tiempo real |

### Monitorizacion

- Alertas automaticas via Discord webhook si:
  - 0 resultados (posible bloqueo del portal)
  - >50% anuncios sin datos basicos (cambio de estructura HTML)
- Reintentos automaticos: 3 intentos con backoff exponencial

## Limites

| Recurso | Limite |
|---------|--------|
| Zonas activas | Sin limite |
| Leads almacenados | Sin limite |
| Usuarios por tenant | Sin limite |
| Portales monitorizados | 4 (habitaclia, fotocasa, milanuncios, idealista) |

## Historial de Cambios

- **Enero 2026**: Optimizacion de schedule (de 6 a 2 scrapes/dia), ahorro 67% credits
