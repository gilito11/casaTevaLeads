"""
PDF Valuation Report Generator for Casa Teva CRM.
Generates professional valuation reports for leads.
"""
import io
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from django.db import connection
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.widgets.markers import makeMarker

logger = logging.getLogger(__name__)

# Brand colors
PRIMARY_COLOR = colors.HexColor('#2563EB')  # Blue-600
SECONDARY_COLOR = colors.HexColor('#1E40AF')  # Blue-800
ACCENT_COLOR = colors.HexColor('#10B981')  # Green-500
TEXT_COLOR = colors.HexColor('#1F2937')  # Gray-800
LIGHT_GRAY = colors.HexColor('#F3F4F6')  # Gray-100
MEDIUM_GRAY = colors.HexColor('#9CA3AF')  # Gray-400


def get_comparables(tenant_id: int, zona: str, precio: float, metros: float, limit: int = 5) -> list:
    """
    Get comparable properties from the same zone with similar characteristics.
    """
    if not zona or not precio or not metros:
        return []

    precio_min = precio * 0.7
    precio_max = precio * 1.3
    metros_min = metros * 0.8
    metros_max = metros * 1.2

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                titulo,
                precio,
                superficie_m2,
                habitaciones,
                source_portal,
                listing_url,
                ubicacion
            FROM public_marts.dim_leads
            WHERE tenant_id = %s
                AND LOWER(zona_clasificada) LIKE %s
                AND precio BETWEEN %s AND %s
                AND superficie_m2 BETWEEN %s AND %s
                AND fecha_primera_captura > NOW() - INTERVAL '90 days'
            ORDER BY
                ABS(precio - %s) + ABS(superficie_m2 - %s) * 100
            LIMIT %s
        """, [
            tenant_id,
            f'%{zona.lower()}%',
            precio_min,
            precio_max,
            metros_min,
            metros_max,
            precio,
            metros,
            limit
        ])

        rows = cursor.fetchall()
        comparables = []
        for row in rows:
            comparables.append({
                'titulo': row[0] or 'Sin titulo',
                'precio': row[1],
                'metros': row[2],
                'habitaciones': row[3],
                'portal': row[4],
                'url': row[5],
                'ubicacion': row[6] or ''
            })

        return comparables


def get_price_history(tenant_id: int, zona: str, days: int = 90) -> list:
    """
    Get price evolution data for a zone over the last N days.
    Returns list of (date, avg_price_m2, count) tuples.
    """
    if not zona:
        return []

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                DATE_TRUNC('week', fecha_primera_captura) as semana,
                AVG(precio / NULLIF(superficie_m2, 0)) as precio_medio_m2,
                COUNT(*) as num_inmuebles
            FROM public_marts.dim_leads
            WHERE tenant_id = %s
                AND LOWER(zona_clasificada) LIKE %s
                AND precio IS NOT NULL
                AND precio > 10000
                AND superficie_m2 IS NOT NULL
                AND superficie_m2 > 20
                AND fecha_primera_captura > NOW() - INTERVAL '%s days'
            GROUP BY DATE_TRUNC('week', fecha_primera_captura)
            ORDER BY semana
        """, [tenant_id, f'%{zona.lower()}%', days])

        rows = cursor.fetchall()
        history = []
        for row in rows:
            if row[1]:
                history.append({
                    'fecha': row[0].strftime('%d/%m') if row[0] else '',
                    'precio_m2': float(row[1]),
                    'count': row[2]
                })

        return history


def create_price_chart(price_history: list, width: float = 450, height: float = 180) -> Drawing:
    """
    Create a line chart showing price evolution.
    """
    drawing = Drawing(width, height)

    if not price_history or len(price_history) < 2:
        # No data - show message
        drawing.add(String(width/2, height/2, "Datos insuficientes para grafico",
                          textAnchor='middle', fontSize=10, fillColor=MEDIUM_GRAY))
        return drawing

    # Background
    drawing.add(Rect(0, 0, width, height, fillColor=LIGHT_GRAY, strokeColor=None))

    chart = HorizontalLineChart()
    chart.x = 50
    chart.y = 30
    chart.width = width - 70
    chart.height = height - 60

    # Data
    prices = [p['precio_m2'] for p in price_history]
    chart.data = [prices]

    # X axis labels
    chart.categoryAxis.categoryNames = [p['fecha'] for p in price_history]
    chart.categoryAxis.labels.angle = 45
    chart.categoryAxis.labels.fontSize = 7
    chart.categoryAxis.labels.boxAnchor = 'ne'

    # Y axis
    min_price = min(prices) * 0.9
    max_price = max(prices) * 1.1
    chart.valueAxis.valueMin = min_price
    chart.valueAxis.valueMax = max_price
    chart.valueAxis.labelTextFormat = '%d'
    chart.valueAxis.labels.fontSize = 8

    # Line style
    chart.lines[0].strokeColor = PRIMARY_COLOR
    chart.lines[0].strokeWidth = 2
    chart.lines[0].symbol = makeMarker('Circle')
    chart.lines[0].symbol.size = 4
    chart.lines[0].symbol.fillColor = PRIMARY_COLOR

    drawing.add(chart)

    # Title
    drawing.add(String(width/2, height - 15, "Evolucion Precio/m2 (ultimos 90 dias)",
                      textAnchor='middle', fontSize=10, fontName='Helvetica-Bold',
                      fillColor=TEXT_COLOR))

    return drawing


class ValuationPDFGenerator:
    """
    Generates professional PDF valuation reports.
    """

    def __init__(self, lead, tenant, valoracion_data: dict):
        self.lead = lead
        self.tenant = tenant
        self.valoracion = valoracion_data
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self):
        """Setup custom paragraph styles."""
        # Override existing 'Title' style
        self.styles['Title'].fontSize = 24
        self.styles['Title'].textColor = PRIMARY_COLOR
        self.styles['Title'].alignment = TA_CENTER
        self.styles['Title'].spaceAfter = 20

        self.styles.add(ParagraphStyle(
            name='Subtitle',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=MEDIUM_GRAY,
            alignment=TA_CENTER,
            spaceAfter=30
        ))

        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=SECONDARY_COLOR,
            spaceBefore=20,
            spaceAfter=10,
            borderColor=PRIMARY_COLOR,
            borderWidth=0,
            borderPadding=5
        ))

        # Override existing 'BodyText' style
        self.styles['BodyText'].fontSize = 10
        self.styles['BodyText'].textColor = TEXT_COLOR
        self.styles['BodyText'].leading = 14

        self.styles.add(ParagraphStyle(
            name='ValuationMain',
            parent=self.styles['Normal'],
            fontSize=28,
            textColor=PRIMARY_COLOR,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))

        self.styles.add(ParagraphStyle(
            name='ValuationRange',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=MEDIUM_GRAY,
            alignment=TA_CENTER
        ))

        self.styles.add(ParagraphStyle(
            name='FooterText',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=MEDIUM_GRAY,
            alignment=TA_CENTER
        ))

    def _build_header(self) -> list:
        """Build report header with logo and date."""
        elements = []

        # Company name as logo placeholder
        header_data = [
            [
                Paragraph(f"<b>{self.tenant.nombre}</b>",
                         ParagraphStyle('Logo', fontSize=18, textColor=PRIMARY_COLOR)),
                Paragraph(f"Fecha: {datetime.now().strftime('%d/%m/%Y')}",
                         ParagraphStyle('Date', fontSize=10, textColor=MEDIUM_GRAY, alignment=TA_RIGHT))
            ]
        ]

        header_table = Table(header_data, colWidths=[10*cm, 7*cm])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))

        elements.append(header_table)
        elements.append(Spacer(1, 10))

        # Horizontal line
        elements.append(HRFlowable(width="100%", thickness=2, color=PRIMARY_COLOR))
        elements.append(Spacer(1, 20))

        # Title
        elements.append(Paragraph("INFORME DE VALORACION", self.styles['Title']))
        elements.append(Paragraph("Analisis comparativo de mercado", self.styles['Subtitle']))

        return elements

    def _build_property_info(self) -> list:
        """Build property information section."""
        elements = []

        elements.append(Paragraph("Datos del Inmueble", self.styles['SectionHeader']))

        # Property details table
        data = []

        if self.lead.direccion:
            data.append(["Direccion:", self.lead.direccion[:80] + ('...' if len(self.lead.direccion or '') > 80 else '')])

        if self.lead.zona_geografica:
            data.append(["Zona:", self.lead.zona_geografica])

        if self.lead.tipo_inmueble:
            data.append(["Tipo:", self.lead.tipo_inmueble.title()])

        if self.lead.metros:
            data.append(["Superficie:", f"{self.lead.metros:,.0f} m2"])

        if self.lead.habitaciones:
            data.append(["Habitaciones:", str(self.lead.habitaciones)])

        if self.lead.banos:
            data.append(["Banos:", str(self.lead.banos)])

        if self.lead.portal:
            data.append(["Portal origen:", self.lead.portal.title()])

        if self.lead.precio:
            data.append(["Precio anunciado:", f"{self.lead.precio:,.0f} EUR"])

        if data:
            table = Table(data, colWidths=[4*cm, 13*cm])
            table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TEXTCOLOR', (0, 0), (0, -1), SECONDARY_COLOR),
                ('TEXTCOLOR', (1, 0), (1, -1), TEXT_COLOR),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GRAY),
                ('BOX', (0, 0), (-1, -1), 1, MEDIUM_GRAY),
            ]))
            elements.append(table)

        return elements

    def _build_valuation_section(self) -> list:
        """Build the main valuation section."""
        elements = []

        elements.append(Spacer(1, 20))
        elements.append(Paragraph("Valoracion Estimada", self.styles['SectionHeader']))

        if not self.valoracion.get('success'):
            elements.append(Paragraph(
                f"No se pudo calcular la valoracion: {self.valoracion.get('error', 'Error desconocido')}",
                self.styles['BodyText']
            ))
            return elements

        # Main valuation box
        valoracion_valor = self.valoracion.get('valoracion', 0)
        valoracion_min = self.valoracion.get('valoracion_min', 0)
        valoracion_max = self.valoracion.get('valoracion_max', 0)

        valuation_data = [
            [Paragraph(f"<b>{valoracion_valor:,.0f} EUR</b>", self.styles['ValuationMain'])],
            [Paragraph(f"Rango: {valoracion_min:,.0f} - {valoracion_max:,.0f} EUR", self.styles['ValuationRange'])],
        ]

        valuation_table = Table(valuation_data, colWidths=[17*cm])
        valuation_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EFF6FF')),  # Blue-50
            ('BOX', (0, 0), (-1, -1), 2, PRIMARY_COLOR),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(valuation_table)
        elements.append(Spacer(1, 15))

        # Valuation details
        details_data = [
            ["Precio/m2 zona:", f"{self.valoracion.get('precio_m2_zona', 0):,.0f} EUR/m2"],
            ["Precio/m2 ajustado:", f"{self.valoracion.get('precio_m2', 0):,.0f} EUR/m2"],
            ["Inmuebles de referencia:", str(self.valoracion.get('num_muestras', 0))],
        ]

        if self.valoracion.get('ajustes'):
            ajustes = self.valoracion['ajustes']
            if ajustes.get('tipo') and ajustes['tipo'] != 1.0:
                details_data.append(["Ajuste por tipo:", f"{(ajustes['tipo'] - 1) * 100:+.0f}%"])
            if ajustes.get('habitaciones') and ajustes['habitaciones'] != 1.0:
                details_data.append(["Ajuste por habitaciones:", f"{(ajustes['habitaciones'] - 1) * 100:+.0f}%"])

        details_table = Table(details_data, colWidths=[6*cm, 5*cm])
        details_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (0, -1), MEDIUM_GRAY),
            ('TEXTCOLOR', (1, 0), (1, -1), TEXT_COLOR),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(details_table)

        return elements

    def _build_comparables_section(self, comparables: list) -> list:
        """Build the comparables section."""
        elements = []

        elements.append(Spacer(1, 20))
        elements.append(Paragraph("Inmuebles Comparables en la Zona", self.styles['SectionHeader']))

        if not comparables:
            elements.append(Paragraph(
                "No se encontraron inmuebles comparables en la zona.",
                self.styles['BodyText']
            ))
            return elements

        # Table header
        header = ["Titulo", "Precio", "m2", "Hab.", "Portal"]
        data = [header]

        for comp in comparables[:5]:
            titulo = comp['titulo'][:35] + ('...' if len(comp['titulo']) > 35 else '')
            precio = f"{comp['precio']:,.0f}" if comp['precio'] else '-'
            metros = f"{comp['metros']:,.0f}" if comp['metros'] else '-'
            habs = str(comp['habitaciones']) if comp['habitaciones'] else '-'
            portal = comp['portal'].title() if comp['portal'] else '-'

            data.append([titulo, precio, metros, habs, portal])

        table = Table(data, colWidths=[7*cm, 3*cm, 2*cm, 2*cm, 3*cm])
        table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            # Body
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TEXTCOLOR', (0, 1), (-1, -1), TEXT_COLOR),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, MEDIUM_GRAY),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(table)

        return elements

    def _build_price_chart_section(self, price_history: list) -> list:
        """Build the price evolution chart section."""
        elements = []

        elements.append(Spacer(1, 20))
        elements.append(Paragraph("Evolucion de Precios en la Zona", self.styles['SectionHeader']))

        chart = create_price_chart(price_history)
        elements.append(chart)

        return elements

    def _build_footer(self) -> list:
        """Build report footer with contact info."""
        elements = []

        elements.append(Spacer(1, 30))
        elements.append(HRFlowable(width="100%", thickness=1, color=MEDIUM_GRAY))
        elements.append(Spacer(1, 10))

        # Contact info
        contact_parts = []
        if self.tenant.comercial_nombre:
            contact_parts.append(self.tenant.comercial_nombre)
        if self.tenant.comercial_email:
            contact_parts.append(self.tenant.comercial_email)
        if self.tenant.comercial_telefono:
            contact_parts.append(self.tenant.comercial_telefono)

        if contact_parts:
            contact_text = " | ".join(contact_parts)
            elements.append(Paragraph(contact_text, self.styles['FooterText']))

        elements.append(Paragraph(
            f"{self.tenant.nombre} - Informe generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}",
            self.styles['FooterText']
        ))

        elements.append(Paragraph(
            "Este informe es orientativo y no constituye una tasacion oficial.",
            self.styles['FooterText']
        ))

        return elements

    def generate(self) -> bytes:
        """
        Generate the PDF report and return as bytes.
        """
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=1.5*cm,
            leftMargin=1.5*cm,
            topMargin=1.5*cm,
            bottomMargin=1.5*cm
        )

        elements = []

        # Build sections
        elements.extend(self._build_header())
        elements.extend(self._build_property_info())
        elements.extend(self._build_valuation_section())

        # Get comparables
        comparables = get_comparables(
            tenant_id=self.lead.tenant_id,
            zona=self.lead.zona_geografica,
            precio=float(self.lead.precio) if self.lead.precio else 0,
            metros=float(self.lead.metros) if self.lead.metros else 0,
            limit=5
        )
        elements.extend(self._build_comparables_section(comparables))

        # Get price history
        price_history = get_price_history(
            tenant_id=self.lead.tenant_id,
            zona=self.lead.zona_geografica,
            days=90
        )
        elements.extend(self._build_price_chart_section(price_history))

        elements.extend(self._build_footer())

        # Build PDF
        doc.build(elements)

        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes


def generate_valuation_pdf(lead, tenant) -> bytes:
    """
    Main entry point to generate a valuation PDF for a lead.

    Args:
        lead: Lead model instance
        tenant: Tenant model instance

    Returns:
        bytes: PDF file content
    """
    from widget.services import valorar_inmueble

    # Calculate valuation
    valoracion = valorar_inmueble(
        zona=lead.zona_geografica or '',
        metros=float(lead.metros) if lead.metros else 0,
        tipo_propiedad=lead.tipo_inmueble or 'piso',
        habitaciones=lead.habitaciones,
        tenant_id=tenant.tenant_id
    )

    # Generate PDF
    generator = ValuationPDFGenerator(lead, tenant, valoracion)
    return generator.generate()
