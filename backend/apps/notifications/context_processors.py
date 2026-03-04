from django.conf import settings


def vapid_public_key(request):
    """Add VAPID public key to template context for PWA push notifications."""
    return {
        'VAPID_PUBLIC_KEY': getattr(settings, 'VAPID_PUBLIC_KEY', '')
    }


def notifications_context(request):
    """Add unread notification count to all templates."""
    if not request.user.is_authenticated:
        return {'notifications_count': 0}

    from notifications.models import Notification
    tenant_id = request.session.get('tenant_id')
    count = Notification.objects.unread_for_user(request.user, tenant_id).count()
    return {'notifications_count': count}
