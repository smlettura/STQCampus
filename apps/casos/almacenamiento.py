"""Guarda los adjuntos cifrados con AES-256-GCM y verifica su integridad con SHA-256 al descargarlos (RF-04, RNF-01).

Con ALMACENAMIENTO=local los objetos se guardan en ADJUNTOS_DIR (desarrollo y pruebas). Con ALMACENAMIENTO=s3
(producción en AWS) se guardan en el bucket privado de Amazon S3 configurado en el almacenamiento «adjuntos», que además
aplica cifrado SSE-KMS. En ambos casos el contenido ya llega cifrado por la aplicación.
"""
import hashlib
import re
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import storages

from apps.core.cifrado import cifrar, descifrar
from apps.core.validadores import nombre_archivo_seguro

from .models import Documento

CONTEXTO = "adjunto"
_CLAVE_VALIDA = re.compile(r"^[0-9a-f]{2}/[0-9a-f]{32}\.bin$")


class AdjuntoAlteradoError(Exception):
    pass


def _en_s3():
    return getattr(settings, "ALMACENAMIENTO", "local") == "s3"


def _clave(ruta_objeto):
    """Solo se aceptan claves generadas por guardar_bytes (evita recorrer otras carpetas o claves del bucket)."""
    if not _CLAVE_VALIDA.match(ruta_objeto or ""):
        raise AdjuntoAlteradoError("Ruta de objeto no válida.")
    return ruta_objeto


def _ruta(ruta_objeto):
    """Ruta en disco del objeto (solo con ALMACENAMIENTO=local)."""
    ruta = (settings.ADJUNTOS_DIR / _clave(ruta_objeto)).resolve()
    if settings.ADJUNTOS_DIR.resolve() not in ruta.parents:
        raise AdjuntoAlteradoError("Ruta de objeto no válida.")
    return ruta


def _escribir(ruta_objeto, contenido):
    if _en_s3():
        storages["adjuntos"].save(_clave(ruta_objeto), ContentFile(contenido))
    else:
        destino = _ruta(ruta_objeto)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(contenido)


def _leer(ruta_objeto):
    if _en_s3():
        with storages["adjuntos"].open(_clave(ruta_objeto), "rb") as f:
            return f.read()
    return _ruta(ruta_objeto).read_bytes()


def guardar_bytes(datos):
    """Cifra y guarda un archivo; devuelve la ruta del objeto y su huella SHA-256."""
    huella = hashlib.sha256(datos).hexdigest()
    ruta_objeto = "%s/%s.bin" % (uuid.uuid4().hex[:2], uuid.uuid4().hex)
    _escribir(ruta_objeto, cifrar(datos, CONTEXTO + ":" + ruta_objeto))
    return ruta_objeto, huella


def leer_bytes(ruta_objeto, huella):
    datos = descifrar(_leer(ruta_objeto), CONTEXTO + ":" + ruta_objeto)
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
    if _en_s3():
        almacen = storages["adjuntos"]
        if almacen.exists(_clave(documento.ruta_objeto)):
            almacen.delete(_clave(documento.ruta_objeto))
        return
    ruta = _ruta(documento.ruta_objeto)
    if ruta.exists():
        ruta.unlink()
