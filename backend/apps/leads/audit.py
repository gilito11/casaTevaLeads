import logging

from .middleware import get_current_user

logger = logging.getLogger(__name__)


def log_audit(accion, lead_id, tenant_id=None, user=None, telefono='', portal='',
              titulo='', estado_anterior='', estado_nuevo='', detalle=''):
    """Escribe un registro de auditoria. Nunca rompe el flujo principal."""
    from .models import AuditLog
    try:
        if user is None:
            user = get_current_user()
        AuditLog.objects.create(
            tenant_id=tenant_id,
            user=user,
            username=user.username if user else '',
            accion=accion,
            lead_id=str(lead_id),
            telefono=telefono or '',
            portal=portal or '',
            titulo=(titulo or '')[:500],
            estado_anterior=estado_anterior or '',
            estado_nuevo=estado_nuevo or '',
            detalle=detalle or '',
        )
    except Exception as e:
        logger.error(f"AuditLog write failed ({accion} {lead_id}): {e}")
