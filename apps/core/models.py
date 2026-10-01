from django.db import models


class Sede(models.Model):
    """Sede del colegio (Central, Prebásica, Básica). El piloto opera en una sola sede."""

    id = models.BigAutoField(primary_key=True, db_column="id_sede")
    nombre = models.CharField("nombre", max_length=60, unique=True)
    direccion = models.CharField("dirección", max_length=160, blank=True)

    class Meta:
        db_table = "sede"
        ordering = ["nombre"]
        verbose_name = "sede"
        verbose_name_plural = "sedes"

    def __str__(self):
        return self.nombre
