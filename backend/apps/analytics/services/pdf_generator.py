"""
Generador de PDF para informes de valoración.

Genera documentos profesionales con:
- Datos del inmueble
- Análisis comparativo de mercado
- Tabla de comparables
- Tendencias de zona
"""
import io
import logging
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from .acm import ACMResult, Comparable

logger = logging.getLogger(__name__)

# Colores corporativos
COLOR_PRIMARY = colors.HexColor('#1e40af')  # Azul oscuro
COLOR_SECONDARY = colors.HexColor('#3b82f6')  # Azul
COLOR_ACCENT = colors.HexColor('#10b981')  # Verde
COLOR_LIGHT = colors.HexColor('#f1f5f9')  # Gris claro
COLOR_DARK = colors.HexColor('#1e293b')  # Gris oscuro


def generar_pdf_valoracion(
    acm: ACMResult,
    nombre_cliente: Optional[str] = None,
    nombre_inmobiliaria: str = "Casa Teva",
    direccion_inmueble: Optional[str] = None,
) -> io.BytesIO:
    """
    Genera un PDF profesional con la valoración del inmueble.

    Args:
        acm: Resultado del análisis comparativo de mercado
        nombre_cliente: Nombre del cliente (opcional)
        nombre_inmobiliaria: Nombre de la inmobiliaria
        direccion_inmueble: Dirección específica del inmueble

    Returns:
        BytesIO con el PDF generado
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    # Estilos
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='TituloDoc',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=COLOR_PRIMARY,
        spaceAfter=20,
        alignment=TA_CENTER
    ))
    styles.add(ParagraphStyle(
        name='Subtitulo',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=COLOR_SECONDARY,
        spaceBefore=15,
        spaceAfter=10
    ))
    styles.add(ParagraphStyle(
        name='Seccion',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=COLOR_DARK,
        spaceBefore=12,
        spaceAfter=6,
        borderColor=COLOR_PRIMARY,
        borderWidth=0,
        borderPadding=0
    ))
    styles.add(ParagraphStyle(
        name='Cuerpo',
        parent=styles['Normal'],
        fontSize=10,
        textColor=COLOR_DARK,
        spaceAfter=8
    ))
    styles.add(ParagraphStyle(
        name='PrecioGrande',
        parent=styles['Normal'],
        fontSize=28,
        textColor=COLOR_ACCENT,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    ))
    styles.add(ParagraphStyle(
        name='PrecioRango',
        parent=styles['Normal'],
        fontSize=12,
        textColor=COLOR_DARK,
        alignment=TA_CENTER
    ))
    styles.add(ParagraphStyle(
        name='Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.gray,
        alignment=TA_CENTER
    ))

    # Contenido
    story = []

    # Header
    story.append(Paragraph(f"INFORME DE VALORACIÓN", styles['TituloDoc']))
    story.append(Paragraph(
        f"<b>{nombre_inmobiliaria}</b> | Generado el {datetime.now().strftime('%d/%m/%Y')}",
        styles['Footer']
    ))
    story.append(Spacer(1, 20))

    # Línea separadora
    story.append(HRFlowable(
        width="100%",
        thickness=2,
        color=COLOR_PRIMARY,
        spaceBefore=5,
        spaceAfter=15
    ))

    # Datos del inmueble
    story.append(Paragraph("DATOS DEL INMUEBLE", styles['Seccion']))

    inmueble_data = [
        ['Zona:', acm.zona],
        ['Tipo:', acm.tipo_inmueble],
        ['Superficie:', f"{acm.metros:.0f} m²"],
    ]
    if acm.habitaciones:
        inmueble_data.append(['Habitaciones:', str(acm.habitaciones)])
    if direccion_inmueble:
        inmueble_data.append(['Dirección:', direccion_inmueble])
    if nombre_cliente:
        inmueble_data.append(['Cliente:', nombre_cliente])

    tabla_inmueble = Table(inmueble_data, colWidths=[4*cm, 12*cm])
    tabla_inmueble.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), COLOR_SECONDARY),
        ('TEXTCOLOR', (1, 0), (1, -1), COLOR_DARK),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
    ]))
    story.append(tabla_inmueble)
    story.append(Spacer(1, 20))

    # Valoración estimada (destacada)
    story.append(HRFlowable(
        width="100%",
        thickness=1,
        color=COLOR_LIGHT,
        spaceBefore=10,
        spaceAfter=10
    ))

    story.append(Paragraph("VALORACIÓN ESTIMADA", styles['Seccion']))
    story.append(Spacer(1, 10))

    # Precio grande
    precio_formateado = f"{acm.precio_estimado:,.0f}".replace(',', '.')
    story.append(Paragraph(f"{precio_formateado} €", styles['PrecioGrande']))

    # Rango de precios
    rango_min = f"{acm.precio_min:,.0f}".replace(',', '.')
    rango_max = f"{acm.precio_max:,.0f}".replace(',', '.')
    story.append(Paragraph(
        f"Rango estimado: {rango_min} € - {rango_max} €",
        styles['PrecioRango']
    ))
    story.append(Spacer(1, 10))

    # Indicadores
    confianza_color = {
        'alta': COLOR_ACCENT,
        'media': colors.orange,
        'baja': colors.red
    }.get(acm.confianza, colors.gray)

    indicadores_data = [
        ['Precio/m²:', f"{acm.precio_m2_medio:,.0f} €/m²".replace(',', '.')],
        ['Comparables:', f"{acm.num_comparables} inmuebles"],
        ['Confianza:', acm.confianza.upper()],
        ['Tendencia:', acm.tendencia_precios.capitalize()],
    ]

    tabla_indicadores = Table(indicadores_data, colWidths=[4*cm, 4*cm])
    tabla_indicadores.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), COLOR_DARK),
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_LIGHT),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOX', (0, 0), (-1, -1), 1, COLOR_SECONDARY),
    ]))

    # Centrar tabla
    wrapper = Table([[tabla_indicadores]], colWidths=[16*cm])
    wrapper.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
    ]))
    story.append(wrapper)
    story.append(Spacer(1, 20))

    # Comparables
    if acm.comparables:
        story.append(HRFlowable(
            width="100%",
            thickness=1,
            color=COLOR_LIGHT,
            spaceBefore=10,
            spaceAfter=10
        ))
        story.append(Paragraph("INMUEBLES COMPARABLES", styles['Seccion']))
        story.append(Paragraph(
            f"Se han analizado {acm.num_comparables} inmuebles similares en la zona para estimar el valor.",
            styles['Cuerpo']
        ))

        # Tabla de comparables
        comp_header = ['Título', 'Precio', 'm²', '€/m²', 'Portal']
        comp_data = [comp_header]

        for c in acm.comparables[:8]:  # Máximo 8 para que quepa
            titulo_corto = c.titulo[:40] + '...' if len(c.titulo) > 40 else c.titulo
            comp_data.append([
                titulo_corto,
                f"{c.precio:,.0f} €".replace(',', '.'),
                f"{c.metros:.0f}",
                f"{c.precio_m2:,.0f}".replace(',', '.'),
                c.portal.capitalize()
            ])

        tabla_comp = Table(comp_data, colWidths=[6*cm, 2.5*cm, 1.5*cm, 2*cm, 2*cm])
        tabla_comp.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            # Body
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            # Alternating rows
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_LIGHT]),
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ]))
        story.append(tabla_comp)

    # Disclaimer
    story.append(Spacer(1, 30))
    story.append(HRFlowable(
        width="100%",
        thickness=1,
        color=COLOR_LIGHT,
        spaceBefore=10,
        spaceAfter=10
    ))

    disclaimer_text = """
    <b>AVISO LEGAL:</b> Este informe de valoración tiene carácter orientativo y se basa en el análisis
    de inmuebles similares actualmente en el mercado. No constituye una tasación oficial y puede variar
    según las características específicas del inmueble, su estado de conservación, y las condiciones
    del mercado en el momento de la venta. Para una tasación oficial, consulte con un tasador homologado.
    """
    story.append(Paragraph(disclaimer_text, ParagraphStyle(
        name='Disclaimer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.gray,
        alignment=TA_LEFT,
        spaceAfter=10
    )))

    # Footer con contacto
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        f"© {datetime.now().year} {nombre_inmobiliaria} | Informe generado automáticamente",
        styles['Footer']
    ))

    # Generar PDF
    doc.build(story)
    buffer.seek(0)

    return buffer


def generar_pdf_lead(
    tenant_id: int,
    lead_id: str,
    nombre_inmobiliaria: str = "Casa Teva"
) -> Optional[io.BytesIO]:
    """
    Genera PDF de valoración para un lead específico.
    """
    from .acm import acm_para_lead

    acm = acm_para_lead(tenant_id, lead_id)
    if not acm:
        logger.warning(f"No se pudo generar ACM para lead {lead_id}")
        return None

    return generar_pdf_valoracion(
        acm=acm,
        nombre_inmobiliaria=nombre_inmobiliaria
    )
