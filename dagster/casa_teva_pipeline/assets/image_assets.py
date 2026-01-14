"""
Assets de análisis de imágenes con Ollama Vision.

Este asset procesa imágenes de leads después del pipeline dbt,
generando un image_score basado en la calidad visual de las fotos.

Solo funciona en entorno local (Ollama no disponible en Azure).
"""
import os
import sys
from typing import Dict, Any

from dagster import (
    asset,
    AssetExecutionContext,
    Output,
    MetadataValue,
)

# Añadir path del proyecto para imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from casa_teva_pipeline.resources.postgres_resource import PostgresResource


def is_ollama_available() -> bool:
    """Verifica si Ollama está disponible localmente."""
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def get_leads_pending_analysis(postgres: PostgresResource, limit: int = 10) -> list:
    """Obtiene leads que tienen fotos pero no han sido analizados."""
    query = """
        SELECT
            dl.lead_id,
            dl.fotos_json,
            dl.titulo
        FROM public_marts.dim_leads dl
        LEFT JOIN public.lead_image_scores lis ON dl.lead_id = lis.lead_id
        WHERE dl.fotos_json IS NOT NULL
          AND json_array_length(dl.fotos_json::json) > 0
          AND lis.lead_id IS NULL
        ORDER BY dl.fecha_primera_captura DESC
        LIMIT %s
    """
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (limit,))
            return cur.fetchall()


def save_image_score(postgres: PostgresResource, lead_id: str, score: int,
                     images_analyzed: int, analysis_json: dict):
    """Guarda el score de imagen en la tabla lead_image_scores."""
    import json
    query = """
        INSERT INTO public.lead_image_scores (lead_id, image_score, images_analyzed, analysis_json)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (lead_id) DO UPDATE SET
            image_score = EXCLUDED.image_score,
            images_analyzed = EXCLUDED.images_analyzed,
            analysis_json = EXCLUDED.analysis_json,
            analyzed_at = NOW()
    """
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (lead_id, score, images_analyzed, json.dumps(analysis_json)))
        conn.commit()


def ensure_image_scores_table(postgres: PostgresResource):
    """Crea la tabla lead_image_scores si no existe."""
    query = """
        CREATE TABLE IF NOT EXISTS public.lead_image_scores (
            lead_id VARCHAR(32) PRIMARY KEY,
            image_score INTEGER NOT NULL DEFAULT 0,
            images_analyzed INTEGER NOT NULL DEFAULT 0,
            analysis_json JSONB,
            analyzed_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_lead_image_scores_score
            ON public.lead_image_scores(image_score DESC);
    """
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
        conn.commit()


@asset(
    description="Analiza imágenes de leads con Ollama Vision para generar image_score",
    compute_kind="python",
    group_name="enrichment",
    deps=["dbt_transform"],
)
def image_analysis(
    context: AssetExecutionContext,
    postgres: PostgresResource,
) -> Output[Dict[str, Any]]:
    """
    Procesa imágenes de leads usando Ollama + Llama 3.2 Vision.

    Solo se ejecuta en entorno local. En Azure, retorna sin procesar.
    Máximo 10 leads por ejecución para no sobrecargar.
    """
    # Verificar si estamos en Azure (no hay Ollama)
    if os.getenv("WEBSITE_SITE_NAME") or os.getenv("CONTAINER_APP_NAME"):
        context.log.info("Entorno Azure detectado - saltando análisis de imágenes (Ollama no disponible)")
        return Output(
            value={"skipped": True, "reason": "Azure environment"},
            metadata={"status": MetadataValue.text("Skipped - Azure environment")}
        )

    # Verificar si Ollama está disponible
    if not is_ollama_available():
        context.log.warning("Ollama no está disponible - saltando análisis de imágenes")
        return Output(
            value={"skipped": True, "reason": "Ollama not available"},
            metadata={"status": MetadataValue.text("Skipped - Ollama not running")}
        )

    context.log.info("Ollama disponible - iniciando análisis de imágenes")

    # Asegurar que la tabla existe
    ensure_image_scores_table(postgres)

    # Importar el analizador de visión
    try:
        from ai_agents.vision_analyzer import analyze_property_images
    except ImportError as e:
        context.log.error(f"Error importando vision_analyzer: {e}")
        return Output(
            value={"error": str(e)},
            metadata={"status": MetadataValue.text("Error - Import failed")}
        )

    # Obtener leads pendientes de análisis
    leads = get_leads_pending_analysis(postgres, limit=10)
    context.log.info(f"Encontrados {len(leads)} leads pendientes de análisis")

    if not leads:
        return Output(
            value={"processed": 0, "skipped": 0, "errors": 0},
            metadata={
                "leads_processed": MetadataValue.int(0),
                "status": MetadataValue.text("No leads pending"),
            }
        )

    processed = 0
    errors = 0

    for lead_id, fotos_json, titulo in leads:
        try:
            # Extraer URLs de fotos (máximo 3 por lead)
            if isinstance(fotos_json, str):
                import json
                fotos = json.loads(fotos_json)
            else:
                fotos = fotos_json

            if not fotos:
                continue

            context.log.info(f"Analizando lead {lead_id[:8]}... ({len(fotos)} fotos)")

            # Analizar imágenes (máximo 3)
            result = analyze_property_images(fotos[:3], max_images=3)

            # Guardar score
            image_score = result.get("total_image_score", 0)
            images_analyzed = result.get("images_analyzed", 0)

            save_image_score(postgres, lead_id, image_score, images_analyzed, result)

            context.log.info(f"Lead {lead_id[:8]}: score={image_score}, fotos={images_analyzed}")
            processed += 1

        except Exception as e:
            context.log.error(f"Error procesando lead {lead_id[:8]}: {e}")
            errors += 1

    return Output(
        value={
            "processed": processed,
            "errors": errors,
            "total_leads": len(leads),
        },
        metadata={
            "leads_processed": MetadataValue.int(processed),
            "leads_with_errors": MetadataValue.int(errors),
            "status": MetadataValue.text(f"Processed {processed}/{len(leads)} leads"),
        }
    )
