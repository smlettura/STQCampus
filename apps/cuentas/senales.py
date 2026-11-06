"""Registra en la bitácora los inicios de sesión y los intentos fallidos (sin guardar el correo ingresado)."""
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver


@receiver(user_logged_in)
def al_iniciar_sesion(sender, request, user, **kwargs):
    from apps.auditoria.servicios import registrar
    registrar(user, "inicio_sesion", "sesion", user.pk, detalle="contraseña correcta", request=request)


@receiver(user_login_failed)
def al_fallar_inicio(sender, credentials, request=None, **kwargs):
    from apps.auditoria.servicios import registrar
    registrar(None, "acceso_denegado", "sesion", None, detalle="credenciales inválidas", request=request)
