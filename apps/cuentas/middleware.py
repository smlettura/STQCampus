"""Obliga a completar el segundo factor antes de acceder a la plataforma (perfiles clínicos, Directora y administrador)."""
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode

RUTAS_LIBRES = ("/cuentas/login", "/cuentas/salir", "/cuentas/2fa/", "/cuentas/restablecer/", "/static/")


class SegundoFactorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if usuario is not None and usuario.is_authenticated and not request.session.get("mfa_ok") \
                and not request.path.startswith(RUTAS_LIBRES) and usuario.requiere_2fa():
            if request.path.startswith("/api/"):
                return JsonResponse({"detalle": "Debe completar el segundo factor."}, status=403)
            destino = "cuentas:verificar_2fa" if usuario.mfa_activo and usuario.secreto_totp else "cuentas:configurar_2fa"
            return redirect(reverse(destino) + "?" + urlencode({"next": request.get_full_path()}))
        return self.get_response(request)


class CambioContrasenaMiddleware:
    """Primer ingreso: quien recibió una contraseña inicial del administrador debe cambiarla antes de continuar."""

    LIBRES = RUTAS_LIBRES + ("/cuentas/cambiar-contrasena/",)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if usuario is not None and usuario.is_authenticated and usuario.cambio_contrasena_pendiente \
                and not request.path.startswith(self.LIBRES) and (request.session.get("mfa_ok") or not usuario.requiere_2fa()):
            if request.path.startswith("/api/"):
                return JsonResponse({"detalle": "Debe cambiar su contraseña inicial."}, status=403)
            return redirect("cuentas:cambiar_contrasena")
        return self.get_response(request)
