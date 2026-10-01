"""Cifrado a nivel de campo con AES-256-GCM (RNF-01).

Formato del texto cifrado: versión (1 byte) | largo del id de clave (1 byte) | id de clave | nonce (12 bytes) | datos+etiqueta.
El «contexto» (tabla.columna) se usa como dato asociado: un valor cifrado copiado a otra columna no se puede descifrar.
Las claves se identifican por id para permitir la rotación: la primera de CIFRADO_CLAVES cifra y todas descifran.
"""
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings

VERSION = b"\x01"


class ErrorDeCifrado(Exception):
    pass


def cifrar(datos, contexto):
    kid = settings.CIFRADO_CLAVE_ACTIVA
    clave = settings.CIFRADO_CLAVES[kid]
    nonce = os.urandom(12)
    kid_b = kid.encode()
    return VERSION + bytes([len(kid_b)]) + kid_b + nonce + AESGCM(clave).encrypt(nonce, bytes(datos), contexto.encode())


def descifrar(token, contexto):
    token = bytes(token)
    if not token.startswith(VERSION) or len(token) < 2:
        raise ErrorDeCifrado("Formato de dato cifrado desconocido.")
    n = token[1]
    kid = token[2:2 + n].decode()
    nonce = token[2 + n:14 + n]
    datos = token[14 + n:]
    clave = settings.CIFRADO_CLAVES.get(kid)
    if clave is None:
        raise ErrorDeCifrado("No está disponible la clave '%s' para descifrar." % kid)
    try:
        return AESGCM(clave).decrypt(nonce, datos, contexto.encode())
    except InvalidTag as exc:
        raise ErrorDeCifrado("El dato cifrado fue alterado o no corresponde a este campo.") from exc


def cifrar_texto(texto, contexto):
    return cifrar(texto.encode("utf-8"), contexto)


def descifrar_texto(token, contexto):
    return descifrar(token, contexto).decode("utf-8")


def id_clave(token):
    token = bytes(token)
    return token[2:2 + token[1]].decode()
