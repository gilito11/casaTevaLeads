"""
Crea un tenant de DEMOSTRACIÓN aislado para capturas de pantalla.

- Duplica ~240 leads del tenant Casa Teva (id=1) en un tenant nuevo "Demo",
  pero ALTERA: estados (con conversiones), nombres de contacto y teléfonos.
- Crea un usuario admin para entrar + varios comerciales con agenda/tareas.
- NO toca el tenant real (Casa Teva). Idempotente: borra y recrea lo del demo.

Uso:  python manage.py seed_demo
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import connection, transaction
from django.utils import timezone

from core.models import Tenant, TenantUser, ZonaGeografica
from leads.models import Task, Contact, Interaction

SOURCE_TENANT = 1            # Casa Teva (origen a duplicar)
N_LEADS = 240               # cuántos leads duplicar
DEMO_PASSWORD = 'FincaDemo2026'

NOMBRES = [
    'Marta Soler', 'Jordi Ferrer', 'Anna Puig', 'Pau Roca', 'Laia Vidal',
    'Sergi Mas', 'Carla Font', 'Oriol Serra', 'Núria Bosch', 'Marc Costa',
    'Elena Ribas', 'David Pons', 'Júlia Camps', 'Albert Roig', 'Sara Vila',
    'Pol Marí', 'Gemma Sala', 'Arnau Prat', 'Clara Soler', 'Roger Capdevila',
]

EMPLEADOS = [
    {'username': 'demo', 'first': 'Eric', 'last': 'Admin', 'rol': 'admin', 'tel': '973000001'},
    {'username': 'laura.demo', 'first': 'Laura', 'last': 'Ferrer', 'rol': 'comercial', 'tel': '973000002'},
    {'username': 'marc.demo', 'first': 'Marc', 'last': 'Soler', 'rol': 'comercial', 'tel': '973000003'},
    {'username': 'nuria.demo', 'first': 'Núria', 'last': 'Vidal', 'rol': 'comercial', 'tel': '973000004'},
]


class Command(BaseCommand):
    help = 'Crea/refresca un tenant Demo con datos de ejemplo para capturas.'

    @transaction.atomic
    def handle(self, *args, **options):
        # 1) Tenant Demo
        tenant, _ = Tenant.objects.get_or_create(
            slug='demo',
            defaults={
                'nombre': 'Inmobiliaria Demo',
                'email_contacto': 'demo@fincaradar.com',
                'telefono': '973 00 00 00',
                'config_scraping': {
                    'zones': ['salou', 'cambrils', 'tarragona', 'reus', 'lleida'],
                    'portals': ['habitaclia', 'fotocasa', 'milanuncios', 'idealista'],
                },
                'activo': True,
                'max_leads_mes': 1000,
                'comercial_nombre': 'Equipo Demo',
                'comercial_email': 'demo@fincaradar.com',
                'comercial_telefono': '973 00 00 00',
            },
        )
        demo_id = tenant.tenant_id
        self.stdout.write(self.style.SUCCESS(f'Tenant Demo id={demo_id}'))

        # 2) Usuarios (admin + comerciales)
        emp_ids = []
        for e in EMPLEADOS:
            u, created = User.objects.get_or_create(
                username=e['username'],
                defaults={
                    'first_name': e['first'], 'last_name': e['last'],
                    'email': f"{e['username']}@fincaradar.com", 'is_active': True,
                    'is_staff': e['rol'] == 'admin',
                },
            )
            u.set_password(DEMO_PASSWORD)
            u.is_active = True
            u.save()
            TenantUser.objects.get_or_create(
                user=u, tenant=tenant,
                defaults={'rol': e['rol'], 'comercial_nombre': f"{e['first']} {e['last']}", 'comercial_telefono': e['tel']},
            )
            emp_ids.append(u.id)
        self.stdout.write(self.style.SUCCESS(f'Usuarios: {[e["username"] for e in EMPLEADOS]}'))

        # 3) Zonas (para la página de configuración)
        for slug in ['salou', 'cambrils', 'tarragona', 'reus', 'lleida']:
            try:
                ZonaGeografica.crear_desde_preestablecida(tenant, slug)
            except Exception:
                pass

        # 4) Leads: borrar demo previos y duplicar de Casa Teva con datos alterados
        with connection.cursor() as cur:
            cur.execute("DELETE FROM leads_lead_estado WHERE tenant_id = %s", [demo_id])
            cur.execute("DELETE FROM public_marts.dim_leads WHERE tenant_id = %s", [demo_id])

            # columnas reales de dim_leads
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema='public_marts' AND table_name='dim_leads'
                ORDER BY ordinal_position
            """)
            cols = [r[0] for r in cur.fetchall()]

            names_arr = "ARRAY[" + ",".join("'" + n.replace("'", "''") + "'" for n in NOMBRES) + "]"
            emp_arr = "ARRAY[" + ",".join(str(i) for i in emp_ids) + "]"
            estado_case = (
                "CASE WHEN f.m < 42 THEN 'NUEVO' "
                "WHEN f.m < 54 THEN 'EN_PROCESO' "
                "WHEN f.m < 66 THEN 'CONTACTADO_SIN_RESPUESTA' "
                "WHEN f.m < 75 THEN 'INTERESADO' "
                "WHEN f.m < 87 THEN 'NO_INTERESADO' "
                "WHEN f.m < 91 THEN 'EN_ESPERA' "
                "WHEN f.m < 94 THEN 'CLIENTE' "
                "WHEN f.m < 96 THEN 'YA_VENDIDO' "
                "ELSE 'NO_CONTACTAR' END"
            )
            # expresiones override por columna
            overrides = {
                'lead_id': "'demo_' || f.lead_id",
                'tenant_id': str(demo_id),
                'telefono_norm': "'6' || lpad(((f.i*123457) % 100000000)::text, 8, '0')",
                'nombre_contacto': f"({names_arr})[(f.i % {len(NOMBRES)}) + 1]",
                'email': "'contacto' || f.i || '@example.com'",
                'estado': estado_case,
                'fecha_primera_captura': "NOW() - ((f.i % 30) || ' days')::interval - ((f.i*37 % 24) || ' hours')::interval",
                'ultima_actualizacion': "NOW()",
                'asignado_a': f"CASE WHEN {estado_case} = 'NUEVO' THEN NULL ELSE ({emp_arr})[(f.i % {len(emp_ids)}) + 1] END",
                'fecha_primer_contacto': f"CASE WHEN {estado_case} = 'NUEVO' THEN NULL ELSE NOW() - ((f.i % 20) || ' days')::interval END",
                'num_contactos': f"CASE WHEN {estado_case} = 'NUEVO' THEN 0 ELSE (f.i % 3) + 1 END",
            }
            select_exprs = [overrides.get(c, f"f.{c}") for c in cols]
            collist = ", ".join('"' + c + '"' for c in cols)
            sql = f"""
                INSERT INTO public_marts.dim_leads ({collist})
                SELECT {", ".join(select_exprs)}
                FROM (
                    SELECT b.*, (b.i % 100) AS m
                    FROM (
                        SELECT d.*, ROW_NUMBER() OVER (ORDER BY fecha_primera_captura DESC NULLS LAST) AS i
                        FROM public_marts.dim_leads d
                        WHERE d.tenant_id = {SOURCE_TENANT}
                        LIMIT {N_LEADS}
                    ) b
                ) f
            """
            cur.execute(sql)
            inserted = cur.rowcount

            # 5) Espejo en leads_lead_estado (consistencia listado/detalle)
            cur.execute("""
                INSERT INTO leads_lead_estado
                    (lead_id, tenant_id, telefono_norm, estado, asignado_a_id,
                     numero_intentos, fecha_primer_contacto, fecha_ultimo_contacto,
                     fecha_cambio_estado, created_at, updated_at)
                SELECT lead_id, tenant_id, telefono_norm, estado, asignado_a,
                       num_contactos, fecha_primer_contacto, fecha_primer_contacto,
                       ultima_actualizacion, NOW(), NOW()
                FROM public_marts.dim_leads
                WHERE tenant_id = %s
                ON CONFLICT (lead_id) DO NOTHING
            """, [demo_id])

            # recoger algunos leads activos para tareas/contactos
            cur.execute("""
                SELECT lead_id, nombre_contacto, telefono_norm, zona_clasificada, estado
                FROM public_marts.dim_leads
                WHERE tenant_id = %s AND estado IN
                  ('EN_PROCESO','CONTACTADO_SIN_RESPUESTA','INTERESADO','EN_ESPERA')
                ORDER BY fecha_primera_captura DESC LIMIT 30
            """, [demo_id])
            activos = cur.fetchall()

        self.stdout.write(self.style.SUCCESS(f'Leads demo insertados: {inserted}'))

        # 6) Agenda/tareas para varios empleados
        Task.objects.filter(tenant=tenant).delete()
        users = list(User.objects.filter(id__in=emp_ids))
        tipos = ['llamar', 'visitar', 'reunion', 'enviar_info', 'seguimiento']
        prios = ['urgente', 'alta', 'media', 'baja']
        rnd = random.Random(42)
        tareas = 0
        for idx, (lead_id, nombre, tel, zona, estado) in enumerate(activos[:24]):
            tipo = tipos[idx % len(tipos)]
            empleado = users[idx % len(users)]
            dias = (idx % 12) - 2  # de hace 2 días a +9 días
            hora = 9 + (idx * 2) % 9   # 9:00 - 18:00
            minuto = (idx * 15) % 60
            venc = timezone.now().replace(hour=hora, minute=minuto, second=0, microsecond=0) + timedelta(days=dias)
            titulos = {
                'llamar': f'Llamar a {nombre or "propietario"}',
                'visitar': f'Visita inmueble en {(zona or "zona").capitalize()}',
                'reunion': 'Reunión de seguimiento de cartera',
                'enviar_info': f'Enviar fichas a {nombre or "propietario"}',
                'seguimiento': f'Seguimiento de {nombre or "lead"}',
            }
            Task.objects.create(
                tenant=tenant, lead_id=lead_id, titulo=titulos[tipo],
                descripcion=f'Lead en estado {estado}. Zona {zona or "-"}.',
                tipo=tipo, prioridad=prios[idx % len(prios)],
                fecha_vencimiento=venc, completada=(dias < 0),
                fecha_completada=(venc if dias < 0 else None),
                asignado_a=empleado, created_by=users[0],
            )
            tareas += 1
        self.stdout.write(self.style.SUCCESS(f'Tareas de agenda creadas: {tareas}'))

        # 7) Contactos + interacciones (página Contactos)
        Contact.objects.filter(tenant=tenant).delete()
        ejemplos = [
            ('Marta Soler', '612000111', 'Busca piso 2-3 hab en Salou, hasta 190.000€.',
             [('llamada', 'Primera llamada, muy interesada en planta baja.', -5),
              ('whatsapp', 'Enviadas 3 fichas, le gustó la de Carrer Major.', -3),
              ('visita', 'Visita realizada, lo quiere pensar.', -1)]),
            ('Jordi Ferrer', '623000222', 'Casa con jardín para familia, zona Cambrils.',
             [('llamada', 'Contacto inicial, mínimo 3 hab.', -7),
              ('email', 'Enviado listado de 5 casas.', -4)]),
            ('Anna Puig', '634000333', 'Inversora, busca pisos para alquilar en costa.',
             [('llamada', 'Presupuesto 300K para 2-3 estudios.', -9),
              ('visita', 'Visita a 4 estudios, interesada en 2.', -2)]),
            ('Pau Roca', '645000444', 'Primera vivienda, necesita asesoría hipotecaria.',
             [('whatsapp', 'Tiene pre-aprobación de 130K.', -3)]),
        ]
        c_count = i_count = 0
        for nombre, tel, notas, inter in ejemplos:
            c = Contact.objects.create(tenant=tenant, telefono=tel, nombre=nombre,
                                       email=None, notas=notas)
            c_count += 1
            for tipo, desc, dago in inter:
                Interaction.objects.create(contact=c, tipo=tipo, descripcion=desc,
                                           fecha=timezone.now() + timedelta(days=dago),
                                           usuario=users[0])
                i_count += 1
        self.stdout.write(self.style.SUCCESS(f'Contactos: {c_count}, interacciones: {i_count}'))

        self.stdout.write(self.style.SUCCESS(
            f'\n=== DEMO LISTO ===\n'
            f'  URL:      fincaradar.com (login)\n'
            f'  Usuario:  demo\n'
            f'  Password: {DEMO_PASSWORD}\n'
            f'  Tenant:   Inmobiliaria Demo (id={demo_id})\n'
            f'  Comerciales extra: laura.demo, marc.demo, nuria.demo (misma password)\n'
        ))
