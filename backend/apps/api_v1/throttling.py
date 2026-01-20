from rest_framework.throttling import BaseThrottle
from django.core.cache import cache
from django.utils import timezone


class TenantRateThrottle(BaseThrottle):
    """
    Rate limiting por tenant basado en la configuracion de APIKey.
    Por defecto: 100 requests/hora (configurable por APIKey).

    Usa cache para tracking de requests.
    """
    cache_format = 'api_throttle_tenant_{tenant_id}'
    default_rate = 100  # requests por hora

    def allow_request(self, request, view):
        # Solo aplica si hay autenticacion por API key
        if not hasattr(request, 'auth') or request.auth is None:
            return True

        api_key = request.auth

        # Obtener rate limit de la API key
        rate_limit = api_key.rate_limit_per_hour or self.default_rate
        tenant_id = api_key.tenant_id

        # Key en cache
        cache_key = self.cache_format.format(tenant_id=tenant_id)

        # Obtener historial de requests (lista de timestamps)
        now = timezone.now()
        one_hour_ago = now.timestamp() - 3600

        history = cache.get(cache_key, [])

        # Filtrar requests del ultima hora
        history = [ts for ts in history if ts > one_hour_ago]

        # Verificar si se excede el limite
        if len(history) >= rate_limit:
            self.wait_seconds = 3600 - (now.timestamp() - history[0])
            return False

        # Agregar request actual
        history.append(now.timestamp())
        cache.set(cache_key, history, timeout=3600)

        # Guardar para wait()
        self.history = history
        self.rate_limit = rate_limit

        return True

    def wait(self):
        """Retorna segundos a esperar antes de permitir otro request."""
        if hasattr(self, 'wait_seconds'):
            return self.wait_seconds
        return None


class TenantBurstThrottle(BaseThrottle):
    """
    Rate limiting para bursts (muchos requests en poco tiempo).
    Limite: 10 requests/segundo por tenant.
    """
    cache_format = 'api_burst_tenant_{tenant_id}'
    rate_per_second = 10

    def allow_request(self, request, view):
        if not hasattr(request, 'auth') or request.auth is None:
            return True

        tenant_id = request.auth.tenant_id
        cache_key = self.cache_format.format(tenant_id=tenant_id)

        now = timezone.now()
        one_second_ago = now.timestamp() - 1

        history = cache.get(cache_key, [])
        history = [ts for ts in history if ts > one_second_ago]

        if len(history) >= self.rate_per_second:
            self.wait_seconds = 1 - (now.timestamp() - history[0])
            return False

        history.append(now.timestamp())
        cache.set(cache_key, history, timeout=2)

        return True

    def wait(self):
        if hasattr(self, 'wait_seconds'):
            return max(0, self.wait_seconds)
        return None
