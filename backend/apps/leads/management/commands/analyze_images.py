"""
Management command to analyze lead images with Ollama Vision.

Usage:
    python manage.py analyze_images               # Analyze up to 10 pending leads
    python manage.py analyze_images --limit 50     # Analyze up to 50 leads
    python manage.py analyze_images --lead abc123  # Analyze a specific lead
    python manage.py analyze_images --reanalyze    # Re-analyze already scored leads
"""
import json
import sys
import os
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import connection

# Add project root to path for ai_agents import
PROJECT_ROOT = str(Path(__file__).resolve().parents[5])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class Command(BaseCommand):
    help = 'Analyze lead images with Ollama + Llama 3.2 Vision to generate image scores'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=10,
                            help='Max leads to analyze (default: 10)')
        parser.add_argument('--lead', type=str, default=None,
                            help='Analyze a specific lead by ID')
        parser.add_argument('--reanalyze', action='store_true',
                            help='Re-analyze leads that already have scores')
        parser.add_argument('--max-images', type=int, default=3,
                            help='Max images per lead (default: 3)')
        parser.add_argument('--portal', type=str, default=None,
                            help='Filter by portal (fotocasa, habitaclia, etc.)')

    def handle(self, *args, **options):
        from ai_agents.vision_analyzer import (
            check_ollama_installed,
            check_model_available,
            analyze_property_images,
        )

        # Check prerequisites
        if not check_ollama_installed():
            self.stderr.write(self.style.ERROR(
                'Ollama not installed or not running. Run: ollama serve'))
            return

        if not check_model_available():
            self.stderr.write(self.style.ERROR(
                'Model llama3.2-vision not found. Run: ollama pull llama3.2-vision'))
            return

        self.stdout.write(self.style.SUCCESS('Ollama + llama3.2-vision ready'))

        # Ensure table exists
        self._ensure_table()

        # Get leads to analyze
        if options['lead']:
            leads = self._get_specific_lead(options['lead'])
        else:
            leads = self._get_pending_leads(options['limit'], options['reanalyze'], options['portal'])

        if not leads:
            self.stdout.write('No leads pending analysis')
            return

        self.stdout.write(f'Found {len(leads)} leads to analyze')

        processed = 0
        errors = 0
        max_images = options['max_images']

        for lead_id, fotos_json, titulo in leads:
            try:
                fotos = json.loads(fotos_json) if isinstance(fotos_json, str) else fotos_json
                if not fotos:
                    continue

                self.stdout.write(f'  Analyzing {lead_id[:12]}... ({len(fotos)} photos, '
                                  f'using {min(len(fotos), max_images)})')

                result = analyze_property_images(fotos[:max_images], max_images=max_images)

                image_score = result.get('total_image_score', 0)
                images_analyzed = result.get('images_analyzed', 0)

                connection.close()  # Reconnect stale Neon connections
                self._save_score(lead_id, image_score, images_analyzed, result)

                self.stdout.write(self.style.SUCCESS(
                    f'    Score: {image_score}/30 ({images_analyzed} images analyzed)'))
                processed += 1

            except Exception as e:
                self.stderr.write(self.style.ERROR(f'    Error: {e}'))
                errors += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nDone: {processed} processed, {errors} errors'))

    def _ensure_table(self):
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS public.lead_image_scores (
                    lead_id VARCHAR(100) PRIMARY KEY,
                    image_score INTEGER NOT NULL DEFAULT 0,
                    images_analyzed INTEGER NOT NULL DEFAULT 0,
                    analysis_json JSONB,
                    analyzed_at TIMESTAMP DEFAULT NOW()
                )
            """)

    def _get_pending_leads(self, limit, reanalyze, portal=None):
        portal_filter = "AND dl.source_portal = %s" if portal else ""
        params = [limit] if not portal else [limit, portal]
        with connection.cursor() as cursor:
            if reanalyze:
                cursor.execute(f"""
                    SELECT dl.lead_id, dl.fotos_json, dl.titulo
                    FROM public_marts.dim_leads dl
                    WHERE dl.fotos_json IS NOT NULL
                      AND dl.fotos_json::text != '[]'
                      AND dl.fotos_json::text != 'null'
                      {portal_filter}
                    ORDER BY dl.fecha_primera_captura DESC
                    LIMIT %s
                """, list(reversed(params)))
            else:
                cursor.execute(f"""
                    SELECT dl.lead_id, dl.fotos_json, dl.titulo
                    FROM public_marts.dim_leads dl
                    LEFT JOIN public.lead_image_scores lis ON dl.lead_id = lis.lead_id
                    WHERE dl.fotos_json IS NOT NULL
                      AND dl.fotos_json::text != '[]'
                      AND dl.fotos_json::text != 'null'
                      AND lis.lead_id IS NULL
                      {portal_filter}
                    ORDER BY dl.fecha_primera_captura DESC
                    LIMIT %s
                """, list(reversed(params)))
            return cursor.fetchall()

    def _get_specific_lead(self, lead_id):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT dl.lead_id, dl.fotos_json, dl.titulo
                FROM public_marts.dim_leads dl
                WHERE dl.lead_id = %s
                  AND dl.fotos_json IS NOT NULL
            """, [lead_id])
            return cursor.fetchall()

    def _save_score(self, lead_id, image_score, images_analyzed, analysis_json):
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO public.lead_image_scores (lead_id, image_score, images_analyzed, analysis_json)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (lead_id) DO UPDATE SET
                    image_score = EXCLUDED.image_score,
                    images_analyzed = EXCLUDED.images_analyzed,
                    analysis_json = EXCLUDED.analysis_json,
                    analyzed_at = NOW()
            """, [lead_id, image_score, images_analyzed, json.dumps(analysis_json)])
