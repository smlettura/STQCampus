"""Avisos por correo sin datos personales: solo invitan a ingresar a la plataforma."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

log = logging.getLogger("bienestar")


def enviar_aviso(usuario, asunto, ruta):
    cuerpo = ("Tiene un aviso nuevo en la %s.\n\nIngrese con su cuenta para revisarlo: %s%s\n\n"
              "Este mensaje no contiene información de estudiantes por resguardo de su privacidad."
              % (settings.NOMBRE_PLATAFORMA, settings.URL_PLATAFORMA, ruta))
    try:
        send_mail(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, [usuario.correo], fail_silently=False)
        return True
    except Exception:  # el aviso queda registrado en la plataforma aunque falle el correo
        log.exception("No se pudo enviar el correo de aviso")
        return False


def avisar_al_confirmar(usuarios, asunto, ruta):
    """Envía los correos solo si la transacción se confirma."""
    for usuario in usuarios:
        transaction.on_commit(lambda u=usuario: enviar_aviso(u, asunto, ruta))
