"""Middleware transversal: contexto de la solicitud (para la bitácora) y cabeceras de seguridad."""
import contextvars

_solicitud_actual = contextvars.ContextVar("solicitud_actual", default=None)


def solicitud_actual():
    return _solicitud_actual.get()


def ip_de(request):
    if request is None:
        return None
    reenviada = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if reenviada:
        return reenviada.split(",")[0].strip()[:45] or None
    return request.META.get("REMOTE_ADDR")


class ContextoSolicitudMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _solicitud_actual.set(request)
        try:
            return self.get_response(request)
        finally:
            _solicitud_actual.reset(token)


class CabecerasSeguridadMiddleware:
    """Política de contenido estricta para scripts y sin caché para páginas con datos personales."""

    CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
           "connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'self'; object-src 'none'")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        respuesta = self.get_response(request)
        respuesta.headers.setdefault("Content-Security-Policy", self.CSP)
        respuesta.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if getattr(request, "user", None) is not None and request.user.is_authenticated:
            respuesta.headers["Cache-Control"] = "no-store"
        return respuesta
