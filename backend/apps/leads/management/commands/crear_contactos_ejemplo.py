"""
Management command para crear contactos de ejemplo
Uso: python manage.py crear_contactos_ejemplo
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from leads.models import Contact, Interaction
from core.models import Tenant


class Command(BaseCommand):
    help = 'Crea contactos de ejemplo para demostración'

    def handle(self, *args, **options):
        tenant = Tenant.objects.first()
        if not tenant:
            self.stderr.write('No hay tenant. Crea uno primero.')
            return

        user = User.objects.first()

        # Datos de contactos de ejemplo
        contactos_data = [
            {
                'telefono': '612345678',
                'nombre': 'María García López',
                'email': 'maria.garcia@email.com',
                'notas': 'Interesada en pisos de 2-3 habitaciones en zona centro. Presupuesto hasta 180.000€.',
                'interacciones': [
                    ('llamada', 'Primera llamada. Muy interesada en ver pisos en Salou. Prefiere planta baja.', -5),
                    ('whatsapp', 'Enviadas 3 fichas de pisos. Le gustó el de Carrer Major.', -3),
                    ('visita', 'Visita al piso de Carrer Major 23. Le encantó pero quiere pensarlo.', -1),
                ]
            },
            {
                'telefono': '623456789',
                'nombre': 'Joan Martínez Puig',
                'email': 'joan.martinez@gmail.com',
                'notas': 'Busca casa con jardín para familia. Tiene 2 hijos pequeños.',
                'interacciones': [
                    ('llamada', 'Contacto inicial. Busca casa unifamiliar con mínimo 3 hab. Zona Cambrils/Salou.', -7),
                    ('email', 'Enviado listado de 5 casas que encajan con sus requisitos.', -5),
                    ('llamada', 'Segunda llamada. Ha descartado 3, quiere ver las otras 2.', -2),
                ]
            },
            {
                'telefono': '634567890',
                'nombre': 'Pedro Sánchez Ruiz',
                'email': None,
                'notas': 'Inversor. Busca pisos para alquilar en zona turística.',
                'interacciones': [
                    ('llamada', 'Primer contacto. Tiene presupuesto de 300K para 2-3 pisos pequeños.', -10),
                    ('nota', 'Revisar disponibilidad de estudios en Miami Platja.', -8),
                    ('whatsapp', 'Confirmado interés. Quiere ver estudios este fin de semana.', -3),
                    ('visita', 'Visita a 4 estudios. Interesado en 2 de ellos.', -1),
                ]
            },
            {
                'telefono': '645678901',
                'nombre': 'Ana Fernández',
                'email': 'anafernandez@hotmail.com',
                'notas': 'Jubilada. Busca piso tranquilo cerca de servicios.',
                'interacciones': [
                    ('llamada', 'Muy amable. Quiere piso con ascensor, máx 2ª planta. Zona céntrica.', -4),
                    ('email', 'Enviadas opciones en Lleida centro con ascensor.', -2),
                ]
            },
            {
                'telefono': '656789012',
                'nombre': 'Carlos y Laura',
                'email': 'carlosylaura2024@gmail.com',
                'notas': 'Pareja joven. Primera vivienda. Buscan hipoteca 100%.',
                'interacciones': [
                    ('llamada', 'Contacto inicial. Presupuesto ajustado ~120K. Necesitan asesoría hipotecaria.', -6),
                    ('nota', 'Derivar a gestoría colaboradora para pre-aprobación hipoteca.', -5),
                    ('whatsapp', 'Confirmado: tienen pre-aprobación de 115K. Podemos buscar opciones.', -2),
                ]
            },
        ]

        created_contacts = 0
        created_interactions = 0

        for data in contactos_data:
            contact, created = Contact.objects.get_or_create(
                tenant=tenant,
                telefono=data['telefono'],
                defaults={
                    'nombre': data['nombre'],
                    'email': data['email'],
                    'notas': data['notas'],
                }
            )

            if created:
                created_contacts += 1
                self.stdout.write(f'  Creado: {contact.nombre} ({contact.telefono})')
            else:
                self.stdout.write(f'  Ya existe: {contact.nombre} ({contact.telefono})')

            # Crear interacciones
            for tipo, desc, days_ago in data['interacciones']:
                fecha = timezone.now() + timedelta(days=days_ago)
                interaction, int_created = Interaction.objects.get_or_create(
                    contact=contact,
                    tipo=tipo,
                    descripcion=desc,
                    defaults={
                        'fecha': fecha,
                        'usuario': user,
                    }
                )
                if int_created:
                    created_interactions += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nCompletado: {created_contacts} contactos, {created_interactions} interacciones creadas'
        ))
