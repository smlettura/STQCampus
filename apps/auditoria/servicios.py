"""Registro y verificación de la bitácora de auditoría."""
import datetime
import json
import os
from contextlib import contextmanager

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from apps.core.middleware import ip_de, solicitud_actual

from .models import EventoAuditoria

HASH_INICIAL = "0" * 64


@contextmanager
def _bloqueo_cadena():
    """Serializa las inserciones para que la cadena de hashes no se bifurque con escrituras concurrentes."""
    if connection.vendor == "mysql":
        with connection.cursor() as c:
            c.execute("SELECT GET_LOCK('bitacora_cadena', 10)")
            obtenido = c.fetchone()[0]
        if obtenido != 1:
            raise RuntimeError("No se pudo obtener el bloqueo de la bitácora.")
        try:
            yield
        finally:
            with connection.cursor() as c:
                c.execute("SELECT RELEASE_LOCK('bitacora_cadena')")
    else:
        yield


def registrar(usuario, accion, entidad, id_entidad=None, detalle="", request=None):
    """Agrega un evento. El detalle nunca debe contener datos personales (solo rutas, códigos o hashes)."""
    request = request or solicitud_actual()
    if usuario is not None and (not getattr(usuario, "is_authenticated", False) or not getattr(usuario, "pk", None)):
        usuario = None
    with _bloqueo_cadena(), transaction.atomic():
        ultimo = EventoAuditoria.objects.order_by("-id").values_list("hash_evento", flat=True).first()
        evento = EventoAuditoria(
            fecha_hora=timezone.now(), usuario=usuario, accion=accion, entidad=entidad[:40],
            id_entidad=id_entidad, detalle=(detalle or "")[:255], ip_origen=(ip_de(request) or "")[:45],
            hash_previo=ultimo or HASH_INICIAL)
        evento.hash_evento = evento.calcular_hash()
        evento.save()
    return evento


def verificar_cadena():
    """Recalcula toda la cadena. Devuelve (íntegra, id del primer evento alterado o None, total revisado)."""
    previo, total = HASH_INICIAL, 0
    for evento in EventoAuditoria.objects.order_by("id").iterator(chunk_size=2000):
        total += 1
        if evento.hash_previo != previo or evento.calcular_hash() != evento.hash_evento:
            return False, evento.id, total
        previo = evento.hash_evento
    return True, None, total


def exportar_dia(fecha):
    """Escribe una copia de los eventos del día en formato JSON Lines y la deja de solo lectura (WORM local).
    En producción el archivo se sube al contenedor «auditoria-inmutable» con política de retención."""
    carpeta = settings.BITACORA_EXPORT_DIR
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / ("bitacora_%s.jsonl" % fecha.isoformat())
    if ruta.exists():
        return ruta, 0
    inicio = timezone.make_aware(datetime.datetime.combine(fecha, datetime.time.min))
    fin = inicio + datetime.timedelta(days=1)
    eventos = EventoAuditoria.objects.filter(fecha_hora__gte=inicio, fecha_hora__lt=fin).order_by("id")
    n = 0
    with open(ruta, "w", encoding="utf-8") as f:
        for e in eventos.iterator():
            f.write(json.dumps({"id": e.id, "fecha_hora": e.fecha_hora.isoformat(), "usuario": e.usuario_id,
                                "accion": e.accion, "entidad": e.entidad, "id_entidad": e.id_entidad,
                                "detalle": e.detalle, "ip": e.ip_origen, "hash_previo": e.hash_previo,
                                "hash_evento": e.hash_evento}, ensure_ascii=False) + "\n")
            n += 1
    os.chmod(ruta, 0o444)
    return ruta, n
