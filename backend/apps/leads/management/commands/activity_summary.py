from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from leads.middleware import _send_telegram
from leads.models import UserSession


class Command(BaseCommand):
    help = "Resumen de actividad del equipo (sesiones de las ultimas 24h + inactivos)"

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=1)
        parser.add_argument('--telegram', action='store_true',
                            help='Enviar el resumen por Telegram ademas de stdout')

    def handle(self, *args, **options):
        now = timezone.now()
        since = now - timedelta(days=options['days'])

        team = User.objects.filter(is_active=True, is_superuser=False) \
            .exclude(username__icontains='demo')
        sessions = UserSession.objects.filter(last_seen__gte=since).order_by('username', 'started_at')

        by_user = {}
        for s in sessions:
            by_user.setdefault(s.username, []).append(s)

        lines = [f"📊 <b>Actividad FincaRadar</b> (ultimas {options['days'] * 24}h)"]
        for user in team:
            user_sessions = by_user.get(user.username)
            if user_sessions:
                ranges = ", ".join(
                    f"{timezone.localtime(s.started_at):%d/%m %H:%M}-{timezone.localtime(s.last_seen):%H:%M}"
                    for s in user_sessions
                )
                lines.append(f"✅ <b>{user.username}</b>: {len(user_sessions)} sesion(es) — {ranges}")
            else:
                last = (UserSession.objects.filter(user_id=user.id)
                        .order_by('-last_seen').first())
                if last:
                    dias = (now - last.last_seen).days
                    lines.append(f"❌ <b>{user.username}</b>: sin actividad (ultima hace {dias}d)")
                else:
                    lines.append(f"❌ <b>{user.username}</b>: nunca registrado")

        text = "\n".join(lines)
        plain = text.replace('<b>', '').replace('</b>', '')
        try:
            self.stdout.write(plain)
        except UnicodeEncodeError:
            self.stdout.write(plain.encode('ascii', 'replace').decode())
        if options['telegram']:
            _send_telegram(text)
