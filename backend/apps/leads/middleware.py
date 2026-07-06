import threading

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
