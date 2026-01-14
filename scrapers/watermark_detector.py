"""
Watermark detection for real estate images.

Detects agency watermarks in the first image to filter out agency listings.
Real estate agencies typically add watermarks in the bottom strip (logo/text).

Strategy:
1. Download first image
2. Analyze bottom 15% for watermark indicators
3. Check for high edge density (text/logos) in corners/bottom
"""

import logging
import requests
from io import BytesIO
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import PIL, gracefully handle if not available
try:
    from PIL import Image, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("PIL not available - watermark detection disabled")


def has_watermark(image_url: str, timeout: int = 10) -> bool:
    """
    Check if an image has a watermark (typically agency logo/text).

    Real estate agency watermarks are commonly placed:
    - Bottom 10-20% strip (most common)
    - Bottom-right corner (logo)
    - Bottom-left corner (text)

    Detection uses edge density - watermarks have more edges than typical
    interior/exterior photos in those regions.

    Args:
        image_url: URL of the image to check
        timeout: Download timeout in seconds

    Returns:
        True if watermark detected, False otherwise
    """
    if not PIL_AVAILABLE:
        return False

    try:
        # Download image
        response = requests.get(image_url, timeout=timeout, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()

        # Open image
        img = Image.open(BytesIO(response.content))

        # Convert to grayscale for edge detection
        if img.mode != 'L':
            img = img.convert('L')

        width, height = img.size

        # Minimum image size check
        if width < 100 or height < 100:
            return False

        # Check bottom strip (15% of image height - common watermark location)
        bottom_strip_height = int(height * 0.15)
        bottom_strip = img.crop((0, height - bottom_strip_height, width, height))

        # Check bottom-right corner (logo location)
        corner_size = min(int(width * 0.25), int(height * 0.15), 150)
        bottom_right = img.crop((width - corner_size, height - corner_size, width, height))

        # Calculate edge density using Sobel-like filter
        bottom_edge_density = _calculate_edge_density(bottom_strip)
        corner_edge_density = _calculate_edge_density(bottom_right)

        # Thresholds determined empirically:
        # - Normal interior photos: ~5-15 edge density
        # - Photos with text watermarks: ~25-50 edge density
        # - Photos with logo watermarks: ~20-40 edge density
        BOTTOM_STRIP_THRESHOLD = 22
        CORNER_THRESHOLD = 28

        has_bottom_watermark = bottom_edge_density > BOTTOM_STRIP_THRESHOLD
        has_corner_watermark = corner_edge_density > CORNER_THRESHOLD

        if has_bottom_watermark or has_corner_watermark:
            logger.debug(
                f"Watermark detected: bottom={bottom_edge_density:.1f}, "
                f"corner={corner_edge_density:.1f}"
            )
            return True

        return False

    except requests.RequestException as e:
        logger.debug(f"Failed to download image for watermark check: {e}")
        return False
    except Exception as e:
        logger.debug(f"Watermark detection error: {e}")
        return False


def _calculate_edge_density(img: 'Image.Image') -> float:
    """
    Calculate edge density of an image region.

    Higher values indicate more edges (text, logos, lines).
    Lower values indicate smooth areas (walls, sky, floors).

    Args:
        img: PIL Image (grayscale)

    Returns:
        Edge density score (0-100)
    """
    # Apply edge detection filter
    edges = img.filter(ImageFilter.FIND_EDGES)

    # Get histogram and calculate mean intensity of edges
    histogram = edges.histogram()
    total_pixels = sum(histogram)

    if total_pixels == 0:
        return 0.0

    # Calculate weighted mean (higher pixel values = more edges)
    weighted_sum = sum(i * count for i, count in enumerate(histogram))
    mean_edge_value = weighted_sum / total_pixels

    # Normalize to 0-100 scale
    return (mean_edge_value / 255) * 100


def check_first_image_for_watermark(
    photos: list,
    timeout: int = 10
) -> Tuple[bool, Optional[str]]:
    """
    Check if the first photo in a listing has a watermark.

    Args:
        photos: List of photo URLs
        timeout: Download timeout

    Returns:
        Tuple of (has_watermark, first_photo_url)
    """
    if not photos:
        return False, None

    first_photo = photos[0]
    has_wm = has_watermark(first_photo, timeout)

    return has_wm, first_photo


# Quick test function
if __name__ == '__main__':
    import sys

    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) > 1:
        url = sys.argv[1]
        result = has_watermark(url)
        print(f"Watermark detected: {result}")
    else:
        print("Usage: python watermark_detector.py <image_url>")
