import json
import logging
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import PushSubscription, AlertPreferences, Notification

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


@login_required
def notification_dropdown_view(request):
    """Return HTMX partial with latest unread notifications."""
    tenant_id = request.session.get('tenant_id')
    notifications = Notification.objects.unread_for_user(request.user, tenant_id)[:10]
    return render(request, 'notifications/partials/dropdown.html', {
        'notifications': notifications,
    })


@login_required
def notification_count_view(request):
    """Return just the badge count for HTMX polling."""
    tenant_id = request.session.get('tenant_id')
    count = Notification.objects.unread_for_user(request.user, tenant_id).count()
    return render(request, 'notifications/partials/badge_count.html', {
        'notifications_count': count,
    })


@login_required
@require_POST
def notification_mark_read_view(request, pk):
    """Mark a single notification as read."""
    try:
        notif = Notification.objects.get(pk=pk)
        if notif.user is None or notif.user == request.user:
            notif.mark_read()
    except Notification.DoesNotExist:
        pass
    # Return updated dropdown
    tenant_id = request.session.get('tenant_id')
    notifications = Notification.objects.unread_for_user(request.user, tenant_id)[:10]
    return render(request, 'notifications/partials/dropdown.html', {
        'notifications': notifications,
    })


@login_required
@require_POST
def notification_mark_all_read_view(request):
    """Mark all notifications as read for current user."""
    tenant_id = request.session.get('tenant_id')
    Notification.objects.unread_for_user(request.user, tenant_id).update(is_read=True)
    return render(request, 'notifications/partials/dropdown.html', {
        'notifications': [],
    })


@login_required
def alert_settings_view(request):
    """View and update alert preferences."""
    prefs = AlertPreferences.get_or_create_for_user(request.user)
    is_htmx = request.headers.get('HX-Request') == 'true'

    if request.method == 'POST':
        # Update preferences from form
        prefs.daily_summary_enabled = request.POST.get('daily_summary_enabled') == 'on'
        prefs.daily_summary_hour = int(request.POST.get('daily_summary_hour', 9))

        prefs.price_drop_enabled = request.POST.get('price_drop_enabled') == 'on'
        prefs.price_drop_threshold = int(request.POST.get('price_drop_threshold', 5))

        prefs.new_leads_enabled = request.POST.get('new_leads_enabled') == 'on'
        prefs.new_leads_min_score = int(request.POST.get('new_leads_min_score', 0))

        prefs.error_alerts_enabled = request.POST.get('error_alerts_enabled') == 'on'
        prefs.task_reminders_enabled = request.POST.get('task_reminders_enabled') == 'on'

        prefs.save()

        if is_htmx:
            return render(request, 'notifications/partials/settings_form.html', {
                'prefs': prefs,
                'saved': True,
            })

        messages.success(request, 'Preferencias de alertas guardadas')
        return redirect('alert_settings')

    context = {
        'prefs': prefs,
    }
    return render(request, 'notifications/alert_settings.html', context)
