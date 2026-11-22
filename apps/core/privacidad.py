"""Modo privado: oculta en pantalla los datos sensibles de estudiantes y apoderados.

El enmascaramiento ocurre en el servidor, al dibujar las plantillas: con el modo activo, los nombres, RUT, contactos,
fechas de nacimiento y textos clínicos no llegan al navegador. Solo afecta a la presentación; la lógica del sistema
(seudonimización del copiloto, exportaciones ARCO+, validaciones) siempre trabaja con los datos reales.
Para volver a ver los datos se exige reautenticación (contraseña y, si corresponde, segundo factor).
"""
from apps.core.middleware import solicitud_actual

CLAVE_SESION = "modo_privado"
OCULTO_TEXTO = "Contenido oculto (modo privado)"
OCULTO_RUT = "••.•••.•••-•"
OCULTO_CONTACTO = "••••••"
OCULTO_FECHA = "••-••-••••"


def activo(request=None):
    request = request or solicitud_actual()
    sesion = getattr(request, "session", None)
    return bool(sesion is not None and sesion.get(CLAVE_SESION))


def iniciales(texto):
    """«Camila Andrea Fuentes Soto» → «C. A. F. S.»; conserva la estructura sin revelar el nombre."""
    partes = [p for p in str(texto or "").replace("—", " ").split() if p and p[0].isalpha()]
    return " ".join("%s." % p[0].upper() for p in partes) or "•••"


def enmascarar(valor, tipo="nombre"):
    if valor in (None, ""):
        return valor
    if tipo == "rut":
        return OCULTO_RUT
    if tipo == "texto":
        return OCULTO_TEXTO
    if tipo == "contacto":
        return OCULTO_CONTACTO
    if tipo == "fecha":
        return OCULTO_FECHA
    return iniciales(valor)


def mostrar(valor, tipo="nombre", request=None):
    """Devuelve el valor tal cual o enmascarado según el modo de la sesión."""
    return enmascarar(valor, tipo) if activo(request) else valor


def datos_visibles(vista=None, *, cuando=None):
    """Decorador para pantallas de edición: los formularios precargados muestran los datos reales en sus campos, así
    que con el modo privado activo primero se pide reautenticación. `cuando(request, *args, **kwargs)` limita el
    control a ciertos casos (por ejemplo, solo al editar un registro existente)."""
    from functools import wraps

    def decorador(funcion):
        @wraps(funcion)
        def envoltura(request, *args, **kwargs):
            if activo(request) and (cuando is None or cuando(request, *args, **kwargs)):
                from django.contrib import messages
                from django.shortcuts import redirect
                from django.urls import reverse
                from django.utils.http import urlencode
                messages.info(request, "Esta pantalla muestra datos sensibles para editarlos: confirme su identidad para continuar.")
                return redirect("%s?%s" % (reverse("cuentas:privacidad_mostrar"), urlencode({"next": request.get_full_path()})))
            return funcion(request, *args, **kwargs)
        return envoltura
    return decorador(vista) if vista is not None else decorador
