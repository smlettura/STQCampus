"""Segundo factor de autenticación con códigos TOTP de 6 dígitos (aplicaciones como Google Authenticator o Microsoft Authenticator)."""
import re
import time

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


def desfase_probable(secreto, codigo, ahora=None):
    """Diagnóstico para la persona: si el código es correcto pero para otra hora, devuelve el desfase en segundos.

    La causa típica es un reloj desajustado en el computador que ejecuta la plataforma o en el teléfono (hora manual o zona
    horaria equivocada). Se revisan ±20 minutos y desfases de horas completas (±14 h). El código NO se acepta: solo se
    usa para explicar el error.
    """
    codigo = re.sub(r"\s", "", codigo or "")
    if not secreto or not re.fullmatch(r"\d{6}", codigo):
        return None
    t, ahora = pyotp.TOTP(secreto), ahora if ahora is not None else time.time()
    candidatos = [k * 30 for k in range(-40, 41) if abs(k) > 1]
    candidatos += [h * 3600 + k * 30 for h in range(-14, 15) if h for k in (-1, 0, 1)]
    for desfase in sorted(candidatos, key=abs):
        if t.at(ahora + desfase) == codigo:
            return desfase
    return None


def mensaje_desfase(desfase):
    minutos = round(abs(desfase) / 60)
    cuanto = ("%d hora%s" % (round(minutos / 60), "s" if round(minutos / 60) != 1 else "")) if minutos >= 55 \
        else ("%d minuto%s" % (minutos, "s" if minutos != 1 else "")) if minutos else "menos de un minuto"
    return ("El código corresponde a otra hora (unos %s de diferencia): el reloj del teléfono o de este computador está "
            "desajustado. Active la hora automática en ambos (en Windows: Configuración › Hora e idioma › «Establecer la "
            "hora automáticamente» y «Sincronizar ahora») e intente con un código nuevo." % cuanto)
