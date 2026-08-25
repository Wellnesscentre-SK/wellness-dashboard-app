from django.contrib.auth import get_user_model
from django.utils.deprecation import MiddlewareMixin
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class DevBypassMiddleware(MiddlewareMixin):
    """Dev-only middleware that bypasses Django auth and sets request.user
    to the first user in the database.

    NOTE: DRF's Request object has its own ``user`` property that calls
    ``_authenticate()`` when ``_user`` is not yet set.  Because
    ``DEFAULT_AUTHENTICATION_CLASSES`` is empty in dev, DRF would otherwise
    overwrite this with ``AnonymousUser``.  The companion
    ``DevBypassAuthentication`` class below plugs into DRF so the bypass
    survives the DRF request cycle.
    """

    def process_request(self, request):
        request.user = get_user_model().objects.first()


class DevBypassAuthentication(BaseAuthentication):
    """DRF authentication backend that mirrors ``DevBypassMiddleware``.

    Returns the first user in the database so that ``request.user`` inside
    DRF views is populated even when no JWT token is supplied.
    """

    def authenticate(self, request):
        user = get_user_model().objects.first()
        if user is None:
            raise AuthenticationFailed("No users found in the database.")
        return (user, None)
