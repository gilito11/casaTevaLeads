from django.conf import settings


def vapid_public_key(request):
    """Add VAPID public key to template context for PWA push notifications."""
    return {
        'VAPID_PUBLIC_KEY': getattr(settings, 'VAPID_PUBLIC_KEY', '')
    }
