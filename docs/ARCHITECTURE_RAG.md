# Arquitectura RAG con Ollama - Casa Teva

> Diseño del sistema Agentic RAG para análisis inteligente de leads inmobiliarios

## Visión General

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SISTEMA ACTUAL                                      │
│  Scrapers → raw_listings → dbt → dim_leads → Django CRM                    │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      NUEVO: CAPA DE IA                                      │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │  Vision Agent   │  │   RAG Agent     │  │  Scoring Agent  │             │
│  │  (Llama Vision) │  │  (LlamaIndex)   │  │  (Orchestrator) │             │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘             │
│           │                    │                    │                       │
│           └────────────────────┼────────────────────┘                       │
│                                │                                            │
│                                ▼                                            │
│                    ┌───────────────────────┐                               │
│                    │    Ollama (Local)     │                               │
│                    │  - llama3.2-vision    │                               │
│                    │  - llama3.2 (text)    │                               │
│                    │  - nomic-embed-text   │                               │
│                    └───────────────────────┘                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Componentes

### 1. Vision Agent (Análisis de Imágenes)

**Propósito**: Analizar fotos de propiedades y generar un `image_score`.

**Modelo**: `llama3.2-vision` (local via Ollama)

**Flujo**:
```
Fotos del lead → Descargar imagen → Base64 → Llama Vision → JSON score
```

**Output**:
```json
{
    "estado_conservacion": 8,
    "calidad_foto": 7,
    "atractivo_visual": 6,
    "tipo_estancia": "salon",
    "image_score": 21
}
```

**Integración**:
- Se ejecuta después del scraping (post-dbt o como job Dagster separado)
- `image_score` (0-30) se suma al `lead_score` existente

### 2. RAG Agent (Búsqueda Semántica)

**Propósito**: Permitir búsquedas en lenguaje natural sobre los leads.

**Stack**:
- **Embeddings**: `nomic-embed-text` (via Ollama)
- **Vector Store**: PostgreSQL + pgvector (ya tienes PostgreSQL)
- **Framework**: LlamaIndex

**Queries de ejemplo**:
```
"Pisos con terraza en Salou por menos de 120.000€"
"Casas reformadas cerca de la playa"
"Propiedades con buenas fotos y precio negociable"
```

**Flujo**:
```
Query usuario → Embedding → pgvector search → Top-K leads → LLM respuesta
```

### 3. Scoring Agent (Orquestador)

**Propósito**: Calcular el score final combinando múltiples señales.

**Fórmula propuesta**:
```
final_score = base_lead_score + image_score + semantic_relevance_score
             (actual, 0-75)    (0-30)        (0-20, para queries)
```

## Arquitectura Técnica

### Diagrama de Componentes

```
┌──────────────────────────────────────────────────────────────┐
│                    Django CRM                                │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │ /leads/    │  │ /search/   │  │ /api/ai/   │             │
│  │ (list)     │  │ (RAG UI)   │  │ (REST API) │             │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘             │
└────────┼───────────────┼───────────────┼────────────────────┘
         │               │               │
         ▼               ▼               ▼
┌──────────────────────────────────────────────────────────────┐
│                   AI Service Layer                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              ai_agents/                              │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │    │
│  │  │vision_analyzer│ │ rag_search   │  │ embedder  │ │    │
│  │  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘ │    │
│  └─────────┼─────────────────┼────────────────┼───────┘    │
│            │                 │                │             │
│            ▼                 ▼                ▼             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                  Ollama API                          │    │
│  │         http://localhost:11434/api/                  │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │    │
│  │  │llama3.2-vision│ │  llama3.2    │  │nomic-embed│ │    │
│  │  │   (8GB)      │  │   (4GB)      │  │   (1GB)   │ │    │
│  │  └──────────────┘  └──────────────┘  └───────────┘ │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
         │                 │
         ▼                 ▼
┌──────────────────────────────────────────────────────────────┐
│                   PostgreSQL                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ dim_leads   │  │ pgvector    │  │ ai_scores   │          │
│  │ (existente) │  │ embeddings  │  │ (nuevo)     │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└──────────────────────────────────────────────────────────────┘
```

### Nuevas Tablas

```sql
-- Almacena embeddings de leads para búsqueda semántica
CREATE TABLE ai_lead_embeddings (
    id SERIAL PRIMARY KEY,
    lead_id VARCHAR(64) REFERENCES public_marts.dim_leads(lead_id),
    embedding vector(768),  -- nomic-embed-text dimension
    text_indexed TEXT,      -- texto usado para embedding
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(lead_id)
);

-- Índice para búsqueda vectorial rápida
CREATE INDEX idx_embeddings_vector ON ai_lead_embeddings
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Almacena scores de imagen por lead
CREATE TABLE ai_image_scores (
    id SERIAL PRIMARY KEY,
    lead_id VARCHAR(64) REFERENCES public_marts.dim_leads(lead_id),
    image_url TEXT,
    estado_conservacion INT,
    calidad_foto INT,
    atractivo_visual INT,
    tipo_estancia VARCHAR(50),
    image_score INT,
    analyzed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(lead_id, image_url)
);
```

## Implementación por Fases

### Fase 1: Vision Agent (1-2 días)
- [x] PoC `vision_analyzer.py`
- [ ] Integrar con Dagster (job post-scraping)
- [ ] Actualizar `lead_score` en dim_leads

### Fase 2: Vector Store (1 día)
- [ ] Instalar pgvector en PostgreSQL
- [ ] Crear tabla `ai_lead_embeddings`
- [ ] Script de indexación inicial

### Fase 3: RAG Search (2-3 días)
- [ ] Implementar `rag_search.py` con LlamaIndex
- [ ] Endpoint API `/api/ai/search/`
- [ ] UI de búsqueda en Django

### Fase 4: Integración (1 día)
- [ ] Combinar scores en vista unificada
- [ ] Dashboard con filtros AI

## Requisitos de Hardware

| Componente | RAM Mínima | RAM Recomendada | GPU |
|------------|------------|-----------------|-----|
| llama3.2-vision | 8 GB | 16 GB | Opcional (CUDA) |
| llama3.2 (text) | 4 GB | 8 GB | Opcional |
| nomic-embed-text | 1 GB | 2 GB | No necesaria |
| pgvector | 1 GB | 4 GB | No |

**Total recomendado**: 16-32 GB RAM, GPU opcional pero mejora 10x velocidad.

## Comandos de Setup

```bash
# 1. Instalar Ollama (Windows/Mac/Linux)
# Descargar desde: https://ollama.com/download

# 2. Descargar modelos
ollama pull llama3.2-vision
ollama pull llama3.2
ollama pull nomic-embed-text

# 3. Verificar instalación
ollama list

# 4. Instalar pgvector en PostgreSQL
# Neon soporta pgvector nativo
# Ejecutar: CREATE EXTENSION vector;

# 5. Instalar dependencias Python
pip install llama-index llama-index-llms-ollama llama-index-embeddings-ollama pgvector

# 6. Probar Vision Agent
python ai_agents/vision_analyzer.py --test
```

## Alternativas Consideradas

| Opción | Pros | Contras |
|--------|------|---------|
| **Ollama (elegida)** | Gratis, local, privacidad | Requiere hardware |
| OpenAI GPT-4V | Mejor calidad | Costoso ($0.01/imagen) |
| Claude Vision | Buena calidad | Costoso |
| Google Gemini | Tier gratis | Límites, latencia |

## Próximos Pasos

1. **Probar PoC**: `python ai_agents/vision_analyzer.py --test`
2. **Instalar Ollama** en tu máquina
3. **Evaluar hardware** disponible
4. Decidir si ejecutar local o en servidor dedicado
