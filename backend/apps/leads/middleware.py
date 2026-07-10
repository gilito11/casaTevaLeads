import logging
import threading
from datetime import timedelta

logger = logging.getLogger(__name__)

_local = threading.local()


def get_current_user():
    """Usuario de la request actual (None fuera de una request, e.g. scripts)."""
    user = getattr(_local, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        return user
    return None


class CurrentUserMiddleware:
    """Guarda el usuario de la request en thread-local para que los signals
    de auditoria puedan atribuir la accion sin acceso a la request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _local.user = getattr(request, 'user', None)
        try:
            return self.get_response(request)
        finally:
            _local.user = None


SESSION_GAP = timedelta(hours=4)
_WRITE_THROTTLE_SECONDS = 60
_IGNORED_PREFIXES = ('/static/', '/media/', '/leads/img/', '/favicon')


def _send_telegram(text):
    from decouple import config
    import requests
    token = config('TELEGRAM_BOT_TOKEN', default='')
    chat_id = config('TELEGRAM_CHAT_ID', default='')
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'},
            timeout=10,
        )
    except Exception as e:
        logger.warning(f"Telegram session alert failed: {e}")


class ActivityTrackingMiddleware:
    """Registra rachas de actividad por usuario en leads_user_session.
    Si pasan mas de 4h entre dos requests se abre una sesion nueva y se
    avisa por Telegram (excepto superusers). Nunca rompe la request."""

    def __init__(self, get_response):
        self.get_response = get_response
        self._last_write = {}  # user_id -> datetime del ultimo write a BD
        self._lock = threading.Lock()

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._track(request)
        except Exception as e:
            logger.error(f"Activity tracking failed: {e}")
        return response

    def _track(self, request):
        user = getattr(request, 'user', None)
        if user is None or not getattr(user, 'is_authenticated', False):
            return
        if request.path.startswith(_IGNORED_PREFIXES):
            return

        from django.utils import timezone
        now = timezone.now()

        # Throttle: un write a BD por usuario por minuto como mucho
        with self._lock:
            last = self._last_write.get(user.id)
            if last and (now - last).total_seconds() < _WRITE_THROTTLE_SECONDS:
                return
            self._last_write[user.id] = now

        from django.db.models import F
        from .models import UserSession

        current = (UserSession.objects
                   .filter(user_id=user.id)
                   .order_by('-last_seen')
                   .first())

        if current and (now - current.last_seen) < SESSION_GAP:
            UserSession.objects.filter(pk=current.pk).update(
                last_seen=now, request_count=F('request_count') + 1)
            return

        UserSession.objects.create(
            user_id=user.id, username=user.username,
            started_at=now, last_seen=now)

        if user.is_superuser:
            return

        local = timezone.localtime(now)
        if current:
            idle = now - current.last_seen
            if idle.days >= 1:
                desde = f"{idle.days}d {idle.seconds // 3600}h sin actividad"
            else:
                desde = f"{idle.seconds // 3600}h {(idle.seconds % 3600) // 60}min sin actividad"
        else:
            desde = "primera actividad registrada"
        threading.Thread(
            target=_send_telegram,
            args=(f"👀 <b>{user.username}</b> ha entrado en FincaRadar\n"
                  f"🕐 {local:%d/%m %H:%M} ({desde})",),
            daemon=True,
        ).start()
