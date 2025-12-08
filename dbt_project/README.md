# Casa Teva dbt Project

dbt (data build tool) project for transforming raw scraped data into clean, structured tables for the Casa Teva Lead System.

## Project Structure

```
dbt_project/
├── dbt_project.yml          # Project configuration
├── profiles.yml             # Database connection profiles
├── models/
│   ├── sources.yml          # Raw data source definitions
│   ├── staging/             # Staging models (views)
│   │   ├── schema.yml       # Staging documentation & tests
│   │   └── stg_fotocasa.sql # Fotocasa staging model
│   └── marts/               # Business logic models (tables)
│       ├── schema.yml       # Marts documentation & tests
│       └── dim_leads.sql    # Leads dimension table (incremental)
└── README.md
```

## Models

### Staging Layer (staging schema)

- **stg_fotocasa**: Extracts and normalizes Fotocasa listings
  - Extracts fields from JSONB `raw_data`
  - Normalizes phone numbers
  - Classifies geographic zones
  - Filters for particular sellers who allow agencies
  - Materialized as VIEW

### Marts Layer (marts schema)

- **dim_leads**: Deduplicated lead dimension table
  - Unions all staging models (Fotocasa, Milanuncios, Wallapop)
  - Deduplicates by `tenant_id + telefono_norm`
  - Adds CRM fields (estado, asignado_a, lead_score)
  - Materialized as INCREMENTAL TABLE

## Setup

### 1. Install dbt

```bash
pip install dbt-postgres
```

### 2. Configure Database Connection

Copy `profiles.yml` to `~/.dbt/profiles.yml` or set environment variables:

```bash
export CASA_TEVA_DB_PASSWORD="your_password"
```

### 3. Test Connection

```bash
cd dbt_project
dbt debug
```

## Usage

### Run all models

```bash
dbt run
```

### Run specific model

```bash
dbt run --select stg_fotocasa
dbt run --select dim_leads
```

### Run tests

```bash
dbt test
```

### Run specific layer

```bash
# Only staging models
dbt run --select staging

# Only marts models
dbt run --select marts
```

### Incremental runs

The `dim_leads` model is incremental. To do a full refresh:

```bash
dbt run --select dim_leads --full-refresh
```

### Generate documentation

```bash
dbt docs generate
dbt docs serve
```

## Model Dependencies

```
raw.raw_listings (source)
    ↓
stg_fotocasa (view)
    ↓
dim_leads (incremental table)
```

## Key Features

### Phone Normalization

Phone numbers are normalized by:
- Removing country code (+34, 0034)
- Removing spaces, parentheses, dashes
- Removing leading zeros

### Zone Classification

Locations are automatically classified into zones:
- Barcelona neighborhoods (Eixample, Gràcia, etc.)
- Metropolitan area cities
- "Otros" for unclassified

### Lead Scoring

Leads are automatically scored (0-100) based on:
- Contact information completeness
- Geographic zone quality

### CRM Fields

New leads are initialized with:
- `estado`: 'NUEVO'
- `asignado_a`: NULL
- `lead_score`: Calculated quality score

## Environment Variables

- `CASA_TEVA_DB_PASSWORD`: Database password (required for prod)
- `CASA_TEVA_DB_HOST`: Database host (default: localhost)
- `CASA_TEVA_DB_PORT`: Database port (default: 5432)
- `CASA_TEVA_DB_USER`: Database user (default: casa_teva)
- `CASA_TEVA_DB_NAME`: Database name (default: casa_teva_db)

## Development Workflow

1. Make changes to models
2. Run affected models: `dbt run --select +my_model`
3. Test changes: `dbt test --select my_model`
4. Generate docs: `dbt docs generate`
5. Commit changes

## Troubleshooting

### Connection issues

```bash
dbt debug
```

### Model failures

```bash
dbt run --select my_model --full-refresh
```

### See compiled SQL

```bash
dbt compile
cat target/compiled/casa_teva/models/staging/stg_fotocasa.sql
```

## TODO

- [ ] Add `stg_milanuncios` model
- [ ] Add `stg_wallapop` model
- [ ] Add analytics models for reporting
- [ ] Add data quality tests
- [ ] Add snapshots for historical tracking
