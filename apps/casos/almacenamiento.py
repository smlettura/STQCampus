"""Guarda los adjuntos cifrados con AES-256-GCM y verifica su integridad con SHA-256 al descargarlos (RF-04, RNF-01).

En producción el mismo contrato se implementa sobre el contenedor «adjuntos» de Azure Blob Storage.
"""
import hashlib
import uuid

from django.conf import settings

from apps.core.cifrado import cifrar, descifrar
from apps.core.validadores import nombre_archivo_seguro

from .models import Documento

CONTEXTO = "adjunto"


class AdjuntoAlteradoError(Exception):
    pass


def _ruta(ruta_objeto):
    ruta = (settings.ADJUNTOS_DIR / ruta_objeto).resolve()
    if settings.ADJUNTOS_DIR.resolve() not in ruta.parents:
        raise AdjuntoAlteradoError("Ruta de objeto no válida.")
    return ruta


def guardar_bytes(datos):
    """Cifra y guarda un archivo; devuelve la ruta del objeto y su huella SHA-256."""
    huella = hashlib.sha256(datos).hexdigest()
    ruta_objeto = "%s/%s.bin" % (uuid.uuid4().hex[:2], uuid.uuid4().hex)
    destino = _ruta(ruta_objeto)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(cifrar(datos, CONTEXTO + ":" + ruta_objeto))
    return ruta_objeto, huella


def leer_bytes(ruta_objeto, huella):
    datos = descifrar(_ruta(ruta_objeto).read_bytes(), CONTEXTO + ":" + ruta_objeto)
    if hashlib.sha256(datos).hexdigest() != huella:
        raise AdjuntoAlteradoError("La huella del archivo no coincide con la registrada.")
    return datos


def guardar_adjunto(archivo, caso, tipo):
    ruta_objeto, huella = guardar_bytes(b"".join(archivo.chunks()))
    return Documento.objects.create(caso=caso, tipo=tipo, nombre_archivo=nombre_archivo_seguro(archivo.name),
                                    ruta_objeto=ruta_objeto, hash_sha256=huella)


def leer_adjunto(documento):
    return leer_bytes(documento.ruta_objeto, documento.hash_sha256)


def eliminar_archivo(documento):
    ruta = _ruta(documento.ruta_objeto)
    if ruta.exists():
        ruta.unlink()
