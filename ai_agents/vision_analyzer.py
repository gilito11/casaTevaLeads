"""
PoC: Análisis de imágenes de propiedades con Ollama + Llama 3.2 Vision.

Este script analiza fotos de inmuebles y genera un score de calidad
que puede usarse para ajustar el lead_score.

Requisitos:
    1. Instalar Ollama: https://ollama.com/download
    2. Descargar modelo: ollama pull llama3.2-vision
    3. pip install requests pillow

Uso:
    python ai_agents/vision_analyzer.py <url_imagen>
    python ai_agents/vision_analyzer.py --test  # Usa imagen de ejemplo
"""

import base64
import json
import logging
import re
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.request import urlopen, Request

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ollama API endpoint (local)
OLLAMA_API = "http://localhost:11434/api/generate"

# Prompt for real estate image analysis
ANALYSIS_PROMPT = """Analiza esta foto de un inmueble en venta. Evalúa los siguientes aspectos y puntúa cada uno de 0 a 10:

1. **Estado de conservación**: ¿La propiedad está reformada, en buen estado, o necesita obras?
2. **Calidad fotográfica**: ¿La foto tiene buena iluminación, enfoque y ángulo profesional?
3. **Atractivo visual**: ¿La decoración, orden y amplitud son atractivos para un comprador?

Responde SOLO con un JSON válido (sin texto adicional):
{
    "estado_conservacion": <0-10>,
    "calidad_foto": <0-10>,
    "atractivo_visual": <0-10>,
    "tipo_estancia": "<salon|dormitorio|cocina|bano|exterior|otro>",
    "observaciones": "<breve descripción de lo que ves>"
}"""


def check_ollama_installed() -> bool:
    """Check if Ollama is installed and running."""
    try:
        result = subprocess.run(
            ['ollama', 'list'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_model_available(model: str = "llama3.2-vision") -> bool:
    """Check if the vision model is downloaded."""
    try:
        result = subprocess.run(
            ['ollama', 'list'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return model in result.stdout
    except:
        return False


def download_image(url: str) -> Optional[bytes]:
    """Download image from URL and return as bytes."""
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        logger.info(f"Descargando imagen: {url[:80]}...")
        req = Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': url.split('/')[0] + '//' + url.split('/')[2] + '/',
        })
        with urlopen(req, timeout=30) as response:
            return response.read()
    except Exception as e:
        logger.error(f"Error descargando imagen: {e}")
        return None


def image_to_base64(image_bytes: bytes) -> str:
    """Convert image bytes to base64 string."""
    return base64.b64encode(image_bytes).decode('utf-8')


def analyze_image_with_ollama(
    image_base64: str,
    model: str = "llama3.2-vision",
    prompt: str = ANALYSIS_PROMPT
) -> Optional[Dict[str, Any]]:
    """
    Send image to Ollama for analysis.

    Args:
        image_base64: Base64-encoded image
        model: Ollama model to use
        prompt: Analysis prompt

    Returns:
        Parsed JSON response or None on error
    """
    import requests

    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_base64],
        "stream": False,
        "options": {
            "temperature": 0.1,  # Low temperature for consistent scoring
        }
    }

    try:
        logger.info(f"Enviando imagen a Ollama ({model})...")
        response = requests.post(
            OLLAMA_API,
            json=payload,
            timeout=300  # Vision models slow, especially first load
        )
        response.raise_for_status()

        result = response.json()
        response_text = result.get('response', '')

        # Try to extract JSON from response
        json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Fallback: parse scores from markdown/text response
        parsed = _parse_scores_from_text(response_text)
        if parsed:
            return parsed

        logger.warning(f"No JSON found in response: {response_text[:200]}")
        return {"raw_response": response_text}

    except requests.exceptions.ConnectionError:
        logger.error("No se puede conectar a Ollama. ¿Está corriendo? (ollama serve)")
        return None
    except requests.exceptions.Timeout:
        logger.error("Timeout esperando respuesta de Ollama")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Error parseando JSON: {e}")
        return {"raw_response": response_text}
    except Exception as e:
        logger.error(f"Error en análisis: {e}")
        return None


def _parse_scores_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Extract scores from markdown/text response when JSON extraction fails."""
    scores = {}
    patterns = {
        'estado_conservacion': r'[Ee]stado\s+(?:de\s+)?conservaci[oó]n[:\s*]+(\d+)',
        'calidad_foto': r'[Cc]alidad\s+fotogr[aá]fica[:\s*]+(\d+)',
        'atractivo_visual': r'[Aa]tractivo\s+visual[:\s*]+(\d+)',
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            scores[key] = min(int(match.group(1)), 10)

    if len(scores) >= 2:
        scores.setdefault('estado_conservacion', 5)
        scores.setdefault('calidad_foto', 5)
        scores.setdefault('atractivo_visual', 5)
        tipo_match = re.search(r'tipo.*?:\s*(sal[oó]n|dormitorio|cocina|ba[nñ]o|exterior|otro)', text, re.IGNORECASE)
        scores['tipo_estancia'] = tipo_match.group(1).lower() if tipo_match else 'otro'
        return scores
    return None


def calculate_image_score(analysis: Dict[str, Any]) -> int:
    """
    Calculate image score (0-30) from analysis results.

    This score can be added to lead_score in dim_leads.
    """
    if not analysis or 'raw_response' in analysis:
        return 0

    estado = analysis.get('estado_conservacion', 0)
    foto = analysis.get('calidad_foto', 0)
    atractivo = analysis.get('atractivo_visual', 0)

    # Weighted average: estado(40%) + foto(30%) + atractivo(30%)
    # Scaled to 0-30 range (max bonus for lead_score)
    score = (estado * 0.4 + foto * 0.3 + atractivo * 0.3) * 3

    return round(score)


def analyze_property_images(
    image_urls: List[str],
    max_images: int = 3
) -> Dict[str, Any]:
    """
    Analyze multiple property images and return aggregate score.

    Args:
        image_urls: List of image URLs
        max_images: Maximum images to analyze (for speed)

    Returns:
        Aggregate analysis with total score
    """
    results = []

    for i, url in enumerate(image_urls[:max_images]):
        logger.info(f"Analizando imagen {i+1}/{min(len(image_urls), max_images)}")

        image_bytes = download_image(url)
        if not image_bytes:
            continue

        image_b64 = image_to_base64(image_bytes)
        analysis = analyze_image_with_ollama(image_b64)

        if analysis:
            analysis['url'] = url
            analysis['image_score'] = calculate_image_score(analysis)
            results.append(analysis)

    if not results:
        return {"error": "No images analyzed", "total_score": 0}

    # Calculate average score across all images
    avg_score = sum(r.get('image_score', 0) for r in results) / len(results)

    return {
        "images_analyzed": len(results),
        "individual_results": results,
        "average_score": round(avg_score),
        "total_image_score": round(avg_score),  # Para sumar a lead_score
    }


def main():
    """Main function for CLI usage."""
    print("=" * 60)
    print("PoC: Análisis de Imágenes con Ollama + Llama 3.2 Vision")
    print("=" * 60)

    # Check prerequisites
    print("\n1. Verificando requisitos...")

    if not check_ollama_installed():
        print("❌ Ollama no está instalado o no está corriendo.")
        print("   Instala desde: https://ollama.com/download")
        print("   Luego ejecuta: ollama serve")
        return 1
    print("✓ Ollama instalado")

    if not check_model_available():
        print("❌ Modelo llama3.2-vision no encontrado.")
        print("   Ejecuta: ollama pull llama3.2-vision")
        return 1
    print("✓ Modelo llama3.2-vision disponible")

    # Get image URL
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            # Test image (public real estate photo)
            image_url = "https://images.habimg.com/imgh/500-6030072/foto1_XXL.jpg"
        else:
            image_url = sys.argv[1]
    else:
        print("\nUso: python vision_analyzer.py <url_imagen>")
        print("     python vision_analyzer.py --test")
        return 1

    # Analyze image
    print(f"\n2. Analizando imagen...")
    print(f"   URL: {image_url[:60]}...")

    image_bytes = download_image(image_url)
    if not image_bytes:
        print("❌ Error descargando imagen")
        return 1

    print(f"   Tamaño: {len(image_bytes) / 1024:.1f} KB")

    image_b64 = image_to_base64(image_bytes)
    analysis = analyze_image_with_ollama(image_b64)

    if not analysis:
        print("❌ Error en análisis")
        return 1

    # Show results
    print("\n3. Resultados del análisis:")
    print("-" * 40)

    if 'raw_response' in analysis:
        print(f"Respuesta raw: {analysis['raw_response'][:500]}")
    else:
        print(f"Estado conservación: {analysis.get('estado_conservacion', 'N/A')}/10")
        print(f"Calidad foto:        {analysis.get('calidad_foto', 'N/A')}/10")
        print(f"Atractivo visual:    {analysis.get('atractivo_visual', 'N/A')}/10")
        print(f"Tipo estancia:       {analysis.get('tipo_estancia', 'N/A')}")
        print(f"Observaciones:       {analysis.get('observaciones', 'N/A')}")

        score = calculate_image_score(analysis)
        print("-" * 40)
        print(f"IMAGE SCORE: {score}/30 puntos")
        print("(Este score se puede sumar al lead_score en dim_leads)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
