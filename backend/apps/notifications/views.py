import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from .models import PushSubscription

logger = logging.getLogger(__name__)


@login_required
@require_POST
@csrf_protect
def subscribe_push(request):
    """
    Subscribe to push notifications.

    Expects POST body:
    {
        "endpoint": "https://...",
        "keys": {
            "p256dh": "...",
            "auth": "..."
        }
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    endpoint = data.get('endpoint')
    keys = data.get('keys', {})
    p256dh = keys.get('p256dh')
    auth = keys.get('auth')

    if not all([endpoint, p256dh, auth]):
        return JsonResponse({'error': 'Missing required fields'}, status=400)

    subscription, created = PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            'user': request.user,
            'p256dh': p256dh,
            'auth': auth,
            'is_active': True
        }
    )

    logger.info(f"Push subscription {'created' if created else 'updated'} for user {request.user.username}")

    return JsonResponse({
        'success': True,
        'created': created,
        'subscription_id': subscription.id
    })


@login_required
@require_POST
@csrf_protect
def unsubscribe_push(request):
    """
    Unsubscribe from push notifications.

    Expects POST body:
    {
        "endpoint": "https://..."
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    endpoint = data.get('endpoint')
    if not endpoint:
        return JsonResponse({'error': 'Missing endpoint'}, status=400)

    deleted, _ = PushSubscription.objects.filter(
        user=request.user,
        endpoint=endpoint
    ).delete()

    return JsonResponse({
        'success': True,
        'deleted': deleted > 0
    })
