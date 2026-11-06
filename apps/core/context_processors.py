from django.conf import settings


def _iniciales(nombre):
    partes = [p for p in (nombre or "").split() if p]
    return "".join(p[0] for p in partes[:2]).upper() or "?"


def plataforma(request):
    datos = {"NOMBRE_PLATAFORMA": settings.NOMBRE_PLATAFORMA, "NOMBRE_COLEGIO": settings.NOMBRE_COLEGIO,
             "NOMBRE_MARCA": settings.NOMBRE_MARCA, "permisos": frozenset(), "mfa_pendiente": False, "menu": []}
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return datos
    datos["roles_usuario"] = usuario.asignaciones_vigentes()
    datos["iniciales"] = _iniciales(usuario.nombre_completo)
    if usuario.requiere_2fa() and not request.session.get("mfa_ok"):
        # Mientras no se complete el segundo factor no se muestra el menú ni ningún dato de la plataforma.
        datos["mfa_pendiente"] = True
        return datos
    datos["permisos"] = usuario.codigos_permiso()
    from apps.alertas.models import Notificacion

    from .menu import construir_menu
    datos["alertas_sin_leer"] = Notificacion.objects.filter(destinatario=usuario, fecha_hora_lectura__isnull=True,
                                                            canal="plataforma").count()
    datos["menu"] = construir_menu(request.path, datos["permisos"], datos["alertas_sin_leer"])
    return datos
