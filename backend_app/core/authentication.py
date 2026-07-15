"""
Custom DRF authentication backend.
Defined in a separate module to avoid circular imports with core.views.
"""
from rest_framework.authentication import BaseAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import AuthenticationFailed


class XTokenAuthentication(BaseAuthentication):
    """
    Accept token via X-Auth-Token header.
    Railway's Hikari edge proxy strips the standard Authorization header,
    so we use this custom header as the primary mechanism and fall back
    to the standard Authorization: Token xxx header as a secondary check.
    """

    def authenticate(self, request):
        raw = request.META.get("HTTP_X_AUTH_TOKEN", "").strip()

        if not raw:
            auth = request.META.get("HTTP_AUTHORIZATION", "").strip()
            if auth.lower().startswith("token "):
                raw = auth[6:].strip()

        if not raw:
            return None

        try:
            token_obj = Token.objects.select_related("user").get(key=raw)
        except Token.DoesNotExist:
            raise AuthenticationFailed("Invalid or expired token.")

        if not token_obj.user.is_active:
            raise AuthenticationFailed("User account is disabled.")

        return (token_obj.user, token_obj)

    def authenticate_header(self, request):
        return "X-Auth-Token"
