from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter

from core.models import TenantUser
from .services import generar_acm, get_ultimo_acm
from .models import ACMReport


def get_tenant_id(user):
    """Obtiene el tenant_id del usuario actual."""
    tenant_user = TenantUser.objects.filter(user=user).first()
    return tenant_user.tenant_id if tenant_user else None


@extend_schema(
    summary="Generar informe ACM",
    description="Genera un nuevo Analisis Comparativo de Mercado para un lead",
    parameters=[
        OpenApiParameter(name='lead_id', type=str, location='path', description='ID del lead'),
    ],
    responses={
        200: {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'report_id': {'type': 'integer'},
                'valoracion_min': {'type': 'integer'},
                'valoracion_max': {'type': 'integer'},
                'valoracion_media': {'type': 'integer'},
                'precio_m2_medio': {'type': 'number'},
                'num_comparables': {'type': 'integer'},
                'confianza': {'type': 'integer'},
            }
        },
        400: {'description': 'Error en la generacion'},
        404: {'description': 'Lead no encontrado'},
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_acm(request, lead_id):
    """Genera un informe ACM para un lead."""
    tenant_id = get_tenant_id(request.user)
    if not tenant_id:
        return Response({'error': 'Usuario sin tenant'}, status=status.HTTP_403_FORBIDDEN)

    result = generar_acm(lead_id, tenant_id, user=request.user)

    if result.get('success'):
        return Response(result)
    else:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary="Obtener ultimo informe ACM",
    description="Obtiene el ultimo informe ACM generado para un lead",
    parameters=[
        OpenApiParameter(name='lead_id', type=str, location='path', description='ID del lead'),
    ],
    responses={
        200: {
            'type': 'object',
            'properties': {
                'id': {'type': 'integer'},
                'lead_id': {'type': 'string'},
                'valoracion_min': {'type': 'number'},
                'valoracion_max': {'type': 'number'},
                'valoracion_media': {'type': 'number'},
                'precio_m2_medio': {'type': 'number'},
                'num_comparables': {'type': 'integer'},
                'confianza': {'type': 'integer'},
                'comparables': {'type': 'array'},
                'created_at': {'type': 'string', 'format': 'date-time'},
            }
        },
        404: {'description': 'No hay informe ACM para este lead'},
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_acm_report(request, lead_id):
    """Obtiene el ultimo informe ACM para un lead."""
    tenant_id = get_tenant_id(request.user)
    if not tenant_id:
        return Response({'error': 'Usuario sin tenant'}, status=status.HTTP_403_FORBIDDEN)

    report = get_ultimo_acm(lead_id, tenant_id)
    if not report:
        return Response({'error': 'No hay informe ACM para este lead'}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        'id': report.id,
        'lead_id': report.lead_id,
        'valoracion_min': float(report.valoracion_min),
        'valoracion_max': float(report.valoracion_max),
        'valoracion_media': float(report.valoracion_media),
        'precio_m2_min': float(report.precio_m2_min) if report.precio_m2_min else None,
        'precio_m2_max': float(report.precio_m2_max) if report.precio_m2_max else None,
        'precio_m2_medio': float(report.precio_m2_medio) if report.precio_m2_medio else None,
        'zona': report.zona,
        'tipo_propiedad': report.tipo_propiedad,
        'superficie_m2': float(report.superficie_m2) if report.superficie_m2 else None,
        'habitaciones': report.habitaciones,
        'precio_anuncio': float(report.precio_anuncio) if report.precio_anuncio else None,
        'num_comparables': report.num_comparables,
        'confianza': report.confianza,
        'metodologia': report.metodologia,
        'comparables': report.comparables,
        'diferencia_precio': report.diferencia_precio,
        'diferencia_pct': report.diferencia_pct,
        'created_at': report.created_at.isoformat(),
        'created_by': report.created_by.get_full_name() if report.created_by else None,
    })


# HTMX view for lead detail page
@login_required
@require_http_methods(['POST'])
def htmx_generate_acm(request, lead_id):
    """Vista HTMX para generar ACM desde la pagina de detalle del lead."""
    tenant_id = get_tenant_id(request.user)
    if not tenant_id:
        return JsonResponse({'error': 'Usuario sin tenant'}, status=403)

    result = generar_acm(lead_id, tenant_id, user=request.user)
    return JsonResponse(result)


@login_required
@require_http_methods(['GET'])
def htmx_get_acm(request, lead_id):
    """Vista HTMX para obtener ACM desde la pagina de detalle del lead."""
    tenant_id = get_tenant_id(request.user)
    if not tenant_id:
        return JsonResponse({'error': 'Usuario sin tenant'}, status=403)

    report = get_ultimo_acm(lead_id, tenant_id)
    if not report:
        return JsonResponse({'exists': False})

    return JsonResponse({
        'exists': True,
        'id': report.id,
        'valoracion_min': int(report.valoracion_min),
        'valoracion_max': int(report.valoracion_max),
        'valoracion_media': int(report.valoracion_media),
        'precio_m2_medio': float(report.precio_m2_medio) if report.precio_m2_medio else None,
        'num_comparables': report.num_comparables,
        'confianza': report.confianza,
        'diferencia_precio': report.diferencia_precio,
        'diferencia_pct': round(report.diferencia_pct, 1) if report.diferencia_pct else None,
        'comparables': report.comparables[:5],  # Solo los 5 primeros para UI
        'created_at': report.created_at.strftime('%d/%m/%Y %H:%M'),
    })
