import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def send_push_notification(subscription, title, body, url=None, tag=None):
    """
    Send a push notification to a single subscription.

    Args:
        subscription: PushSubscription model instance
        title: Notification title
        body: Notification body text
        url: Optional URL to open on click
        tag: Optional tag to group notifications

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.error("pywebpush not installed")
        return False

    vapid_private_key = getattr(settings, 'VAPID_PRIVATE_KEY', None)
    vapid_claims = getattr(settings, 'VAPID_CLAIMS', None)

    if not vapid_private_key or not vapid_claims:
        logger.error("VAPID keys not configured")
        return False

    payload = {
        "title": title,
        "body": body,
        "tag": tag or "casa-teva",
        "data": {"url": url or "/"}
    }

    try:
        webpush(
            subscription_info=subscription.get_subscription_info(),
            data=json.dumps(payload),
            vapid_private_key=vapid_private_key,
            vapid_claims=vapid_claims
        )
        return True
    except WebPushException as e:
        logger.error(f"Push notification failed: {e}")
        if e.response and e.response.status_code in (404, 410):
            subscription.is_active = False
            subscription.save(update_fields=['is_active'])
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending push: {e}")
        return False


def send_push_to_user(user, title, body, url=None, tag=None):
    """
    Send push notification to all active subscriptions of a user.

    Args:
        user: User model instance
        title: Notification title
        body: Notification body text
        url: Optional URL to open on click
        tag: Optional tag to group notifications

    Returns:
        int: Number of successful notifications sent
    """
    from .models import PushSubscription

    subscriptions = PushSubscription.objects.filter(user=user, is_active=True)
    sent = 0

    for sub in subscriptions:
        if send_push_notification(sub, title, body, url, tag):
            sent += 1

    return sent


def send_push_to_tenant(tenant_id, title, body, url=None, tag=None):
    """
    Send push notification to all users of a tenant.

    Args:
        tenant_id: Tenant ID
        title: Notification title
        body: Notification body text
        url: Optional URL to open on click
        tag: Optional tag to group notifications

    Returns:
        int: Number of successful notifications sent
    """
    from .models import PushSubscription
    from core.models import TenantUser

    user_ids = TenantUser.objects.filter(
        tenant_id=tenant_id,
        is_active=True
    ).values_list('user_id', flat=True)

    subscriptions = PushSubscription.objects.filter(
        user_id__in=user_ids,
        is_active=True
    )
    sent = 0

    for sub in subscriptions:
        if send_push_notification(sub, title, body, url, tag):
            sent += 1

    return sent
