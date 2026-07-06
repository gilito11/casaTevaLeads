from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from .audit import log_audit
from .models import LeadEstado


@receiver(pre_save, sender=LeadEstado)
def _capture_old_estado(sender, instance, **kwargs):
    instance._old_estado = None
    if instance.pk:
        old = LeadEstado.objects.filter(pk=instance.pk).values_list('estado', flat=True).first()
        instance._old_estado = old


@receiver(post_save, sender=LeadEstado)
def _log_estado_change(sender, instance, created, **kwargs):
    old = getattr(instance, '_old_estado', None)
    if created:
        log_audit(
            'estado_creado', instance.lead_id,
            tenant_id=instance.tenant_id,
            telefono=instance.telefono_norm,
            estado_nuevo=instance.estado,
        )
    elif old is not None and old != instance.estado:
        log_audit(
            'estado_cambiado', instance.lead_id,
            tenant_id=instance.tenant_id,
            telefono=instance.telefono_norm,
            estado_anterior=old,
            estado_nuevo=instance.estado,
        )


@receiver(post_delete, sender=LeadEstado)
def _log_estado_delete(sender, instance, **kwargs):
    log_audit(
        'estado_borrado', instance.lead_id,
        tenant_id=instance.tenant_id,
        telefono=instance.telefono_norm,
        estado_anterior=instance.estado,
        detalle=f"intentos={instance.numero_intentos}, ultimo_contacto={instance.fecha_ultimo_contacto}",
    )
