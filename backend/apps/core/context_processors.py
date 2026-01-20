"""
Context processors for core app.
"""
from django.utils import timezone


def tasks_context(request):
    """
    Add task counts to template context for sidebar badges.
    """
    if not request.user.is_authenticated:
        return {}

    try:
        from leads.models import Task
        from core.models import TenantUser

        tenant_id = request.session.get('tenant_id')
        if not tenant_id:
            tenant_user = TenantUser.objects.filter(user=request.user).first()
            if tenant_user:
                tenant_id = tenant_user.tenant.tenant_id

        if not tenant_id:
            return {}

        hoy = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Tareas para hoy sin completar
        tareas_hoy_count = Task.objects.filter(
            tenant_id=tenant_id,
            completada=False,
            fecha_vencimiento__date=hoy.date()
        ).count()

        # Tareas vencidas
        tareas_vencidas_count = Task.objects.filter(
            tenant_id=tenant_id,
            completada=False,
            fecha_vencimiento__lt=hoy
        ).count()

        return {
            'tareas_hoy_count': tareas_hoy_count,
            'tareas_vencidas_count': tareas_vencidas_count,
        }

    except Exception:
        return {}
