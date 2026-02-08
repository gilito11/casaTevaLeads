"""
Error handling utilities for Casa Teva scrapers.

Provides:
- Retry logic with exponential backoff
- Webhook alerting (Discord/Telegram)
- Data quality validation
- Error categorization
"""

import logging
import os
import time
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar
from zoneinfo import ZoneInfo

import requests

# Timezone for alerts (Spain/Madrid)
MADRID_TZ = ZoneInfo('Europe/Madrid')


def get_madrid_time() -> datetime:
    """Get current time in Madrid timezone."""
    return datetime.now(MADRID_TZ)

logger = logging.getLogger(__name__)

# Type variable for generic retry decorator
T = TypeVar('T')


# =============================================================================
# RETRY LOGIC
# =============================================================================

class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        retryable_exceptions: tuple = (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
        ),
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retryable_exceptions = retryable_exceptions


def retry_with_backoff(config: Optional[RetryConfig] = None):
    """
    Decorator for retry with exponential backoff.

    Usage:
        @retry_with_backoff(RetryConfig(max_attempts=3))
        def fetch_page(url):
            ...
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e

                    if attempt == config.max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {config.max_attempts} attempts: {e}"
                        )
                        raise

                    delay = min(
                        config.initial_delay * (config.exponential_base ** (attempt - 1)),
                        config.max_delay
                    )
                    logger.warning(
                        f"{func.__name__} attempt {attempt}/{config.max_attempts} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                except Exception as e:
                    # Non-retryable exception, raise immediately
                    logger.error(f"{func.__name__} failed with non-retryable error: {e}")
                    raise

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


# =============================================================================
# WEBHOOK ALERTING
# =============================================================================

class AlertSeverity:
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


def get_webhook_url() -> Optional[str]:
    """Get webhook URL from environment."""
    return os.environ.get('ALERT_WEBHOOK_URL')


def send_alert(
    title: str,
    message: str,
    severity: str = AlertSeverity.ERROR,
    details: Optional[Dict[str, Any]] = None,
    webhook_url: Optional[str] = None,
) -> bool:
    """
    Send alert via webhook (Discord/Telegram/Slack compatible).

    Args:
        title: Alert title
        message: Alert message
        severity: Alert severity level
        details: Additional details dict
        webhook_url: Override webhook URL (uses env var if None)

    Returns:
        True if alert sent successfully
    """
    url = webhook_url or get_webhook_url()

    if not url:
        logger.debug("No webhook URL configured, skipping alert")
        return False

    # Emoji based on severity
    emoji_map = {
        AlertSeverity.INFO: "ℹ️",
        AlertSeverity.WARNING: "⚠️",
        AlertSeverity.ERROR: "❌",
        AlertSeverity.CRITICAL: "🚨",
    }
    emoji = emoji_map.get(severity, "📋")

    timestamp = get_madrid_time().strftime("%Y-%m-%d %H:%M:%S")

    # Build message content
    content_parts = [
        f"{emoji} **{title}**",
        f"_{severity.upper()}_ - {timestamp}",
        "",
        message,
    ]

    if details:
        content_parts.append("")
        content_parts.append("**Details:**")
        for key, value in details.items():
            content_parts.append(f"• {key}: `{value}`")

    content = "\n".join(content_parts)

    # Try Discord format first
    payload = {"content": content}

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=10,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code in (200, 204):
            logger.info(f"Alert sent: {title}")
            return True
        else:
            logger.warning(f"Webhook returned {response.status_code}: {response.text[:100]}")
            return False

    except Exception as e:
        logger.error(f"Failed to send alert: {e}")
        return False


def alert_on_failure(
    alert_title: str,
    include_traceback: bool = True,
):
    """
    Decorator that sends alert when function fails.

    Usage:
        @alert_on_failure("Scraper failed")
        def scrape_portal():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                import traceback

                details = {
                    "function": func.__name__,
                    "error_type": type(e).__name__,
                }

                message = str(e)
                if include_traceback:
                    tb = traceback.format_exc()
                    # Truncate traceback if too long
                    if len(tb) > 500:
                        tb = tb[-500:]
                    message = f"{message}\n\n```\n{tb}\n```"

                send_alert(
                    title=alert_title,
                    message=message,
                    severity=AlertSeverity.ERROR,
                    details=details,
                )
                raise

        return wrapper
    return decorator


# =============================================================================
# EMAIL ALERTING
# =============================================================================

def send_email_alert(
    subject: str,
    body: str,
    severity: str = AlertSeverity.ERROR,
    recipient: Optional[str] = None,
) -> bool:
    """
    Send alert via SendGrid API.

    Args:
        subject: Email subject
        body: Email body (plain text)
        severity: Alert severity for subject prefix
        recipient: Override recipient email

    Returns:
        True if email sent successfully

    Requires env var: SENDGRID_API_KEY
    """
    api_key = os.environ.get('SENDGRID_API_KEY')
    if not api_key:
        logger.debug("SendGrid not configured (missing SENDGRID_API_KEY)")
        return False

    to_email = recipient or os.environ.get('ALERT_EMAIL_TO', 'ericgc11@hotmail.com')
    from_email = os.environ.get('ALERT_EMAIL_FROM', 'alertas@casateva.es')

    # Severity prefix
    prefix_map = {
        AlertSeverity.INFO: "[INFO]",
        AlertSeverity.WARNING: "[WARNING]",
        AlertSeverity.ERROR: "[ERROR]",
        AlertSeverity.CRITICAL: "[CRITICAL]",
    }
    prefix = prefix_map.get(severity, "[ALERT]")

    # Add timestamp to body
    full_body = f"""{body}

---
Timestamp: {get_madrid_time().strftime('%Y-%m-%d %H:%M:%S')} (Europe/Madrid)
Environment: {'Production' if os.environ.get('FLY_APP_NAME') else 'Local'}
"""

    try:
        response = requests.post(
            'https://api.sendgrid.com/v3/mail/send',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'personalizations': [{'to': [{'email': to_email}]}],
                'from': {'email': from_email, 'name': 'Casa Teva Alertas'},
                'subject': f"{prefix} Casa Teva Scrapers: {subject}",
                'content': [{'type': 'text/plain', 'value': full_body}],
            },
            timeout=10,
        )

        if response.status_code in (200, 202):
            logger.info(f"Email alert sent to {to_email}: {subject}")
            return True
        else:
            logger.warning(f"SendGrid returned {response.status_code}: {response.text[:200]}")
            return False

    except Exception as e:
        logger.error(f"Failed to send email alert: {e}")
        return False


def send_html_change_alert(
    portal: str,
    issue_type: str,
    details: str,
    metrics: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Send alert specifically for HTML structure changes.

    Args:
        portal: Portal name (fotocasa, habitaclia, etc.)
        issue_type: Type of issue (no_results, missing_fields, blocked, etc.)
        details: Detailed description
        metrics: Optional metrics dict (field_fill_rates, etc.)

    Returns:
        True if alert sent
    """
    subject = f"{portal.upper()} - Posible cambio de HTML ({issue_type})"

    body = f"""
ALERTA: Detectado posible cambio en la estructura HTML de {portal}

Tipo de problema: {issue_type}
Portal: {portal}

Detalles:
{details}
"""

    if metrics:
        body += "\nMétricas:\n"
        for key, value in metrics.items():
            body += f"  - {key}: {value}\n"

    body += """
Acciones recomendadas:
1. Verificar manualmente el portal
2. Revisar los selectores CSS/XPath en el scraper
3. Actualizar el código si es necesario
"""

    # Send both email and webhook
    email_sent = send_email_alert(subject, body, AlertSeverity.WARNING)
    webhook_sent = send_alert(
        title=subject,
        message=details,
        severity=AlertSeverity.WARNING,
        details=metrics,
    )

    return email_sent or webhook_sent


# =============================================================================
# VALUE VALIDATION
# =============================================================================

def validate_listing_data(listing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and clean individual listing data.

    Checks:
    - Price in valid range (1,000 - 10,000,000 EUR)
    - Phone format (9 digits for Spain)
    - URL is valid
    - Required fields present

    Returns:
        Cleaned listing dict with validation flags
    """
    errors = []

    # Validate price
    precio = listing.get('precio')
    if precio is not None:
        try:
            precio_num = float(precio)
            if precio_num < 1000:
                errors.append(f"Price too low: {precio_num}")
                listing['_precio_invalid'] = True
            elif precio_num > 10000000:
                errors.append(f"Price too high: {precio_num}")
                listing['_precio_invalid'] = True
        except (ValueError, TypeError):
            errors.append(f"Invalid price format: {precio}")
            listing['_precio_invalid'] = True

    # Validate phone (Spanish format: 9 digits starting with 6, 7, 8, or 9)
    telefono = listing.get('telefono_norm')
    if telefono:
        telefono_clean = ''.join(filter(str.isdigit, str(telefono)))
        if len(telefono_clean) != 9:
            errors.append(f"Invalid phone length: {telefono}")
            listing['telefono_norm'] = None
        elif telefono_clean[0] not in '6789':
            errors.append(f"Invalid phone prefix: {telefono}")
            listing['telefono_norm'] = None

    # Validate URL
    url = listing.get('url')
    if url and not url.startswith(('http://', 'https://')):
        errors.append(f"Invalid URL: {url}")
        listing['_url_invalid'] = True

    # Validate metros (1 - 10000 m2)
    metros = listing.get('metros')
    if metros is not None:
        try:
            metros_num = float(metros)
            if metros_num < 1 or metros_num > 10000:
                listing['metros'] = None
        except (ValueError, TypeError):
            listing['metros'] = None

    listing['_validation_errors'] = errors
    listing['_is_valid'] = len(errors) == 0

    return listing


def validate_batch(listings: List[Dict[str, Any]], portal: str) -> List[Dict[str, Any]]:
    """
    Validate a batch of listings and log summary.

    Args:
        listings: List of listing dicts
        portal: Portal name for logging

    Returns:
        List of validated listings (invalid ones marked but not removed)
    """
    validated = [validate_listing_data(l) for l in listings]

    valid_count = sum(1 for l in validated if l.get('_is_valid', True))
    invalid_count = len(validated) - valid_count

    if invalid_count > 0:
        logger.warning(
            f"{portal}: {invalid_count}/{len(validated)} listings have validation errors"
        )

    return validated


# =============================================================================
# DATA QUALITY VALIDATION
# =============================================================================

class DataQualityResult:
    """Result of data quality check."""

    def __init__(self):
        self.passed = True
        self.warnings: List[str] = []
        self.errors: List[str] = []
        self.metrics: Dict[str, Any] = {}

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.passed = False

    def set_metric(self, key: str, value: Any):
        self.metrics[key] = value

    def __bool__(self):
        return self.passed


def validate_scraping_results(
    listings: List[Dict[str, Any]],
    portal_name: str,
    expected_min_count: int = 1,
    required_fields: Optional[List[str]] = None,
    alert_on_failure: bool = True,
) -> DataQualityResult:
    """
    Validate scraping results for data quality issues.

    Args:
        listings: List of scraped listings
        portal_name: Name of portal for alert context
        expected_min_count: Minimum expected listings
        required_fields: Fields that should not be null
        alert_on_failure: Send alert if validation fails

    Returns:
        DataQualityResult with validation status
    """
    if required_fields is None:
        required_fields = ['titulo', 'precio', 'url']

    result = DataQualityResult()

    # Check total count
    total = len(listings)
    result.set_metric('total_listings', total)

    if total == 0:
        result.add_error(f"No listings found for {portal_name}")
    elif total < expected_min_count:
        result.add_warning(
            f"Low listing count for {portal_name}: {total} (expected >= {expected_min_count})"
        )

    if total == 0:
        if alert_on_failure:
            send_alert(
                title=f"Data Quality Alert: {portal_name}",
                message="No listings were scraped",
                severity=AlertSeverity.ERROR,
                details={"portal": portal_name, "count": 0},
            )
        return result

    # Check field completeness
    field_null_counts = {field: 0 for field in required_fields}

    for listing in listings:
        for field in required_fields:
            value = listing.get(field)
            if value is None or value == '' or value == []:
                field_null_counts[field] += 1

    # Calculate null percentages
    for field, null_count in field_null_counts.items():
        null_pct = (null_count / total) * 100
        result.set_metric(f'{field}_null_pct', round(null_pct, 1))

        if null_pct > 50:
            result.add_error(
                f"Critical: {field} is null in {null_pct:.1f}% of listings"
            )
        elif null_pct > 20:
            result.add_warning(
                f"Warning: {field} is null in {null_pct:.1f}% of listings"
            )

    # Check for phone extraction rate
    phones_found = sum(1 for l in listings if l.get('telefono_norm'))
    phone_rate = (phones_found / total) * 100
    result.set_metric('phone_extraction_rate', round(phone_rate, 1))

    if phone_rate < 10:
        result.add_warning(f"Low phone extraction rate: {phone_rate:.1f}%")

    # Check for particulares rate
    particulares = sum(1 for l in listings if l.get('es_particular', False))
    particular_rate = (particulares / total) * 100
    result.set_metric('particular_rate', round(particular_rate, 1))

    if particular_rate < 50:
        result.add_warning(f"Low particular rate: {particular_rate:.1f}% (might be scraping agencies)")

    # Detect HTML structure change indicators
    html_change_indicators = []
    if total == 0:
        html_change_indicators.append("no_results")
    if result.metrics.get('titulo_null_pct', 0) > 50:
        html_change_indicators.append("missing_titles")
    if result.metrics.get('precio_null_pct', 0) > 50:
        html_change_indicators.append("missing_prices")

    # Send alert if there are errors (possible HTML change)
    if not result.passed and alert_on_failure:
        if html_change_indicators:
            # Send HTML change alert (email + webhook)
            send_html_change_alert(
                portal=portal_name,
                issue_type=", ".join(html_change_indicators),
                details="\n".join(result.errors),
                metrics={
                    "portal": portal_name,
                    "total_listings": total,
                    **result.metrics,
                },
            )
        else:
            # Regular alert (webhook only)
            send_alert(
                title=f"Data Quality Alert: {portal_name}",
                message="\n".join(result.errors),
                severity=AlertSeverity.ERROR,
                details={
                    "portal": portal_name,
                    "total_listings": total,
                    **result.metrics,
                },
            )
    elif result.warnings and alert_on_failure:
        send_alert(
            title=f"Data Quality Warning: {portal_name}",
            message="\n".join(result.warnings),
            severity=AlertSeverity.WARNING,
            details={
                "portal": portal_name,
                "total_listings": total,
                **result.metrics,
            },
        )

    return result


# =============================================================================
# SCRAPING REPORT
# =============================================================================

def generate_scraping_report(
    portal_results: Dict[str, Dict[str, Any]],
    send_summary: bool = True,
) -> Dict[str, Any]:
    """
    Generate summary report of scraping run.

    Args:
        portal_results: Dict of {portal_name: stats_dict}
        send_summary: Send summary alert

    Returns:
        Summary report dict
    """
    total_leads = 0
    total_errors = 0
    portals_with_errors = []

    for portal, stats in portal_results.items():
        total_leads += stats.get('listings_saved', 0)
        errors = stats.get('errors', 0)
        total_errors += errors
        if errors > 0:
            portals_with_errors.append(f"{portal} ({errors})")

    report = {
        'timestamp': get_madrid_time().isoformat(),
        'total_leads': total_leads,
        'total_errors': total_errors,
        'portals_processed': len(portal_results),
        'portals_with_errors': portals_with_errors,
        'portal_details': portal_results,
    }

    if send_summary:
        if total_errors > 0:
            send_alert(
                title="Scraping Complete (with errors)",
                message=f"Scraped {total_leads} leads with {total_errors} errors",
                severity=AlertSeverity.WARNING,
                details={
                    'total_leads': total_leads,
                    'portals_with_errors': ', '.join(portals_with_errors) or 'None',
                },
            )
        elif total_leads > 0:
            send_alert(
                title="Scraping Complete",
                message=f"Successfully scraped {total_leads} leads from {len(portal_results)} portals",
                severity=AlertSeverity.INFO,
                details={'total_leads': total_leads},
            )

    return report
