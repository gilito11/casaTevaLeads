from rest_framework import authentication, exceptions
from .models import APIKey


class APIKeyAuthentication(authentication.BaseAuthentication):
    """
    Autenticacion por API Key via header X-API-Key.

    Uso:
        X-API-Key: ctv_xxxxx...

    El request.user sera None pero request.auth contendra la APIKey.
    El tenant se obtiene desde request.auth.tenant.
    """
    keyword = 'X-API-Key'

    def authenticate(self, request):
        api_key = request.headers.get(self.keyword)

        if not api_key:
            return None  # No hay key, dejar que otro auth maneje

        api_key_obj = APIKey.get_by_key(api_key)

        if api_key_obj is None:
            raise exceptions.AuthenticationFailed('API Key invalida o expirada')

        if not api_key_obj.is_active:
            raise exceptions.AuthenticationFailed('API Key desactivada')

        # Registrar uso (async seria mejor para produccion)
        api_key_obj.record_usage()

        # Retornar (user, auth) - user es None porque no hay usuario Django
        return (None, api_key_obj)

    def authenticate_header(self, request):
        """Retorna el nombre del header para WWW-Authenticate."""
        return self.keyword


class APIKeyUser:
    """
    Pseudo-usuario para representar una API key autenticada.
    Se usa cuando se necesita un objeto similar a User.
    """
    def __init__(self, api_key: APIKey):
        self.api_key = api_key
        self.tenant = api_key.tenant
        self.is_authenticated = True
        self.is_anonymous = False

    @property
    def id(self):
        return f"apikey_{self.api_key.id}"

    def __str__(self):
        return f"APIKey: {self.api_key.name}"
