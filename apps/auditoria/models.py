"""Bitácora de auditoría de solo inserción, encadenada por hash (RF-10, RNF-03).

La aplicación no permite modificar ni eliminar eventos. En MySQL, además, el usuario de base de datos de la aplicación
solo tiene permisos SELECT e INSERT sobre esta tabla (ver `python manage.py permisos_bd`).
"""
import datetime
import hashlib

from django.conf import settings
from django.db import models


class BitacoraInmutableError(Exception):
    pass


class EventoQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise BitacoraInmutableError("La bitácora de auditoría no admite modificaciones.")

    def delete(self):
        raise BitacoraInmutableError("La bitácora de auditoría no admite eliminaciones.")


class EventoAuditoria(models.Model):
    ACCIONES = [
        ("inicio_sesion", "Inicio de sesión"),
        ("consulta", "Consulta"),
        ("creacion", "Creación"),
        ("modificacion", "Modificación"),
        ("exportacion", "Exportación"),
        ("eliminacion", "Eliminación"),
        ("acceso_denegado", "Acceso denegado"),
    ]

    id = models.BigAutoField(primary_key=True, db_column="id_evento")
    fecha_hora = models.DateTimeField("fecha y hora", db_index=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                related_name="eventos", db_column="id_usuario")
    accion = models.CharField("acción", max_length=20, choices=ACCIONES)
    entidad = models.CharField("entidad", max_length=40)
    id_entidad = models.BigIntegerField("id de la entidad", null=True, blank=True)
    detalle = models.CharField("detalle", max_length=255, blank=True)
    ip_origen = models.CharField("IP de origen", max_length=45, blank=True)
    hash_previo = models.CharField("hash previo", max_length=64)
    hash_evento = models.CharField("hash del evento", max_length=64, unique=True)

    objects = EventoQuerySet.as_manager()

    class Meta:
        db_table = "evento_auditoria"
        ordering = ["-id"]
        verbose_name = "evento de auditoría"
        verbose_name_plural = "bitácora de auditoría"

    def __str__(self):
        return "%s · %s · %s" % (self.fecha_hora, self.get_accion_display(), self.entidad)

    def calcular_hash(self):
        partes = [self.hash_previo, self.fecha_hora.astimezone(datetime.timezone.utc).isoformat(timespec="microseconds"), str(self.usuario_id or ""),
                  self.accion, self.entidad, str(self.id_entidad or ""), self.detalle, self.ip_origen]
        return hashlib.sha256("|".join(partes).encode("utf-8")).hexdigest()

    def save(self, *args, **kwargs):
        if self.pk is not None or not self._state.adding:
            raise BitacoraInmutableError("La bitácora de auditoría no admite modificaciones.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise BitacoraInmutableError("La bitácora de auditoría no admite eliminaciones.")
