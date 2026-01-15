{{
    config(
        materialized='table',
        schema='staging',
        tags=['staging', 'images'],
        pre_hook="CREATE TABLE IF NOT EXISTS public.lead_image_scores (lead_id VARCHAR(32) PRIMARY KEY, image_score INTEGER DEFAULT 0, images_analyzed INTEGER DEFAULT 0, analysis_json JSONB, analyzed_at TIMESTAMP DEFAULT NOW())"
    )
}}

/*
    Staging model for lead image scores.

    This creates the table if it doesn't exist (via pre_hook)
    and provides a view of existing scores.

    The actual scores are populated by the image_analysis Dagster asset.
*/

SELECT
    lead_id,
    image_score,
    images_analyzed,
    analysis_json,
    analyzed_at
FROM public.lead_image_scores
