"""Segundo factor de autenticación con códigos TOTP de 6 dígitos (aplicaciones como Google Authenticator o Microsoft Authenticator)."""
import re

import pyotp
import qrcode
import qrcode.image.svg
from django.core.cache import cache

EMISOR = "STQCampus Bienestar"


def nuevo_secreto():
    return pyotp.random_base32()


def uri_aprovisionamiento(correo, secreto):
    return pyotp.TOTP(secreto).provisioning_uri(name=correo, issuer_name=EMISOR)


def qr_svg(uri):
    imagen = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
    svg = imagen.to_string(encoding="unicode")
    return re.sub(r"<\?xml[^>]*\?>", "", svg)


def verificar_codigo(secreto, codigo, id_usuario):
    """Valida el código y evita que el mismo código se reutilice (ataques de repetición)."""
    codigo = re.sub(r"\s", "", codigo or "")
    if not secreto or not re.fullmatch(r"\d{6}", codigo):
        return False
    if not pyotp.TOTP(secreto).verify(codigo, valid_window=1):
        return False
    return cache.add("totp_usado:%s:%s" % (id_usuario, codigo), True, timeout=120)
