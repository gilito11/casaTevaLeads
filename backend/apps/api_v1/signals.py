import hmac
import hashlib
import json
import logging
import requests
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Webhook, WebhookDelivery

logger = logging.getLogger(__name__)


def generate_signature(payload: dict, secret: str) -> str:
    """Genera firma HMAC-SHA256 para el payload."""
    payload_str = json.dumps(payload, sort_keys=True, default=str)
    signature = hmac.new(
        secret.encode(),
        payload_str.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"sha256={signature}"


def send_webhook(webhook: Webhook, event_type: str, payload: dict):
    """
    Envia un webhook y registra el resultado.
    """
    if not webhook.is_active:
        return

    # Añadir metadata al payload
    full_payload = {
        'event': event_type,
        'timestamp': timezone.now().isoformat(),
        'data': payload
    }

    signature = generate_signature(full_payload, webhook.secret)

    headers = {
        'Content-Type': 'application/json',
        'X-Webhook-Signature': signature,
        'X-Webhook-Event': event_type,
    }

    delivery = WebhookDelivery(
        webhook=webhook,
        event_type=event_type,
        payload=full_payload
    )

    start_time = timezone.now()

    try:
        response = requests.post(
            webhook.url,
            json=full_payload,
            headers=headers,
            timeout=10
        )
        duration_ms = int((timezone.now() - start_time).total_seconds() * 1000)

        delivery.status_code = response.status_code
        delivery.response_body = response.text[:1000]  # Limitar tamaño
        delivery.duration_ms = duration_ms

        if 200 <= response.status_code < 300:
            delivery.success = True
            webhook.record_success(response.status_code)
        else:
            delivery.success = False
            delivery.error = f"HTTP {response.status_code}"
            webhook.record_failure(response.status_code)

    except requests.RequestException as e:
        duration_ms = int((timezone.now() - start_time).total_seconds() * 1000)
        delivery.success = False
        delivery.error = str(e)[:500]
        delivery.duration_ms = duration_ms
        webhook.record_failure()
        logger.error(f"Webhook error: {webhook.url} - {e}")

    delivery.save()


def trigger_new_lead_webhook(tenant, lead_data: dict):
    """Dispara webhooks de nuevo lead para un tenant."""
    webhooks = Webhook.objects.filter(
        tenant=tenant,
        event_type='new_lead',
        is_active=True
    )

    for webhook in webhooks:
        try:
            send_webhook(webhook, 'new_lead', lead_data)
        except Exception as e:
            logger.error(f"Error enviando webhook {webhook.id}: {e}")


def trigger_status_change_webhook(tenant, lead_id: str, old_estado: str, new_estado: str):
    """Dispara webhooks de cambio de estado para un tenant."""
    webhooks = Webhook.objects.filter(
        tenant=tenant,
        event_type='status_change',
        is_active=True
    )

    payload = {
        'lead_id': lead_id,
        'old_estado': old_estado,
        'new_estado': new_estado,
    }

    for webhook in webhooks:
        try:
            send_webhook(webhook, 'status_change', payload)
        except Exception as e:
            logger.error(f"Error enviando webhook {webhook.id}: {e}")


def trigger_price_drop_webhook(tenant, lead_data: dict, precio_anterior: float, precio_nuevo: float):
    """Dispara webhooks de bajada de precio para un tenant."""
    webhooks = Webhook.objects.filter(
        tenant=tenant,
        event_type='price_drop',
        is_active=True
    )

    payload = {
        **lead_data,
        'precio_anterior': precio_anterior,
        'precio_nuevo': precio_nuevo,
        'cambio_pct': ((precio_nuevo - precio_anterior) / precio_anterior) * 100
    }

    for webhook in webhooks:
        try:
            send_webhook(webhook, 'price_drop', payload)
        except Exception as e:
            logger.error(f"Error enviando webhook {webhook.id}: {e}")
