"""Esquema reservado para el módulo de IA (DER-C): el equipo lo está entrenando y aún no genera contenido.

Las tablas quedan creadas para que la integración futura no cambie el modelo de datos: contenido generado, llamadas
al modelo, fuentes normativas y retroalimentación (RF-16 a RF-19). Ver `apps/ia/servicios.py`.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.campos import TextoCifrado
from apps.core.validadores import validar_texto_minimo


class DocumentoNormativo(models.Model):
    TIPOS = [("reglamento_interno", "Reglamento interno"), ("manual_convivencia", "Manual de convivencia"),
             ("circular_superintendencia", "Circular de la Superintendencia"), ("ley_decreto", "Ley o decreto")]

    id = models.BigAutoField(primary_key=True, db_column="id_documento_norm")
    titulo = models.CharField("título", max_length=200)
    tipo = models.CharField("tipo", max_length=30, choices=TIPOS)
    fuente = models.CharField("fuente", max_length=255, help_text="URL o referencia del documento original.")
    version = models.CharField("versión", max_length=20)
    fecha_vigencia = models.DateField("fecha de vigencia")
    vigente = models.BooleanField("vigente", default=True)

    class Meta:
        db_table = "documento_normativo"
        ordering = ["titulo"]
        constraints = [models.UniqueConstraint(fields=["titulo", "version"], name="uq_documento_normativo_version")]

    def __str__(self):
        return "%s (v%s)" % (self.titulo, self.version)


class FragmentoNormativo(models.Model):
    id = models.BigAutoField(primary_key=True, db_column="id_fragmento")
    documento = models.ForeignKey(DocumentoNormativo, on_delete=models.CASCADE, related_name="fragmentos",
                                  db_column="id_documento_norm")
    seccion = models.CharField("sección", max_length=120)
    texto = models.TextField("texto")
    embedding = models.BinaryField("vector del fragmento",
                                   help_text="Vector de términos serializado para la recuperación de contexto.")

    class Meta:
        db_table = "fragmento_normativo"
        ordering = ["documento", "id"]

    def __str__(self):
        return "%s · %s" % (self.documento.titulo, self.seccion)


class ContenidoIA(models.Model):
    TIPOS = [("borrador_informe", "Borrador de informe"), ("resumen", "Resumen cronológico con evidencias")]
    ESTADOS = [("generado", "Generado — pendiente de validación"), ("validado", "Validado por una profesional"),
               ("descartado", "Descartado")]

    id = models.BigAutoField(primary_key=True, db_column="id_contenido")
    caso = models.ForeignKey("casos.Caso", on_delete=models.CASCADE, related_name="contenidos_ia", db_column="id_caso")
    solicitante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="contenidos_ia",
                                    db_column="id_solicitante")
    tipo = models.CharField("tipo", max_length=20, choices=TIPOS)
    modelo = models.CharField("modelo", max_length=60)
    texto_generado = TextoCifrado("texto generado")
    etiqueta_ia = models.BooleanField("marcado como generado con IA", default=True, editable=False)
    estado = models.CharField("estado", max_length=12, choices=ESTADOS, default="generado")
    validador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                  related_name="contenidos_validados", db_column="id_validador")
    fecha_generacion = models.DateTimeField("fecha de generación", default=timezone.now)
    fecha_validacion = models.DateTimeField("fecha de validación", null=True, blank=True)

    class Meta:
        db_table = "contenido_ia"
        ordering = ["-fecha_generacion"]
        verbose_name = "contenido generado con IA"
        verbose_name_plural = "contenidos generados con IA"
        constraints = [
            # RF-18: un contenido validado siempre registra quién y cuándo lo validó.
            models.CheckConstraint(
                condition=~Q(estado="validado") | (Q(validador__isnull=False) & Q(fecha_validacion__isnull=False)),
                name="ck_contenido_ia_validacion"),
        ]

    def __str__(self):
        return "%s · %s" % (self.get_tipo_display(), self.caso.estudiante)

    def clean(self):
        if self.estado == "validado" and (not self.validador_id or not self.fecha_validacion):
            raise ValidationError("Un contenido validado debe registrar a la profesional que lo validó y la fecha.")


class LlamadaModelo(models.Model):
    id = models.BigAutoField(primary_key=True, db_column="id_llamada")
    contenido = models.ForeignKey(ContenidoIA, on_delete=models.CASCADE, related_name="llamadas", db_column="id_contenido")
    proveedor = models.CharField("proveedor", max_length=40)
    modelo = models.CharField("modelo", max_length=60)
    tokens_entrada = models.PositiveIntegerField("tokens de entrada", default=0)
    tokens_salida = models.PositiveIntegerField("tokens de salida", default=0)
    hash_carga = models.CharField("hash del texto enviado", max_length=64)
    fecha_hora = models.DateTimeField("fecha y hora", default=timezone.now)

    class Meta:
        db_table = "llamada_modelo"
        ordering = ["-fecha_hora"]


class ContenidoIAFuente(models.Model):
    contenido = models.ForeignKey(ContenidoIA, on_delete=models.CASCADE, related_name="fuentes", db_column="id_contenido")
    fragmento = models.ForeignKey(FragmentoNormativo, on_delete=models.CASCADE, related_name="usos",
                                  db_column="id_fragmento")
    relevancia = models.DecimalField("relevancia", max_digits=4, decimal_places=3)

    class Meta:
        db_table = "contenido_ia_fuente"
        ordering = ["-relevancia"]
        constraints = [
            models.UniqueConstraint(fields=["contenido", "fragmento"], name="uq_contenido_fuente"),
            models.CheckConstraint(condition=Q(relevancia__gte=0) & Q(relevancia__lte=1), name="ck_fuente_relevancia"),
        ]


class RetroalimentacionIA(models.Model):
    MOTIVOS = [("incorrecta", "Incorrecta"), ("problematica", "Problemática")]

    id = models.BigAutoField(primary_key=True, db_column="id_retro")
    contenido = models.ForeignKey(ContenidoIA, on_delete=models.CASCADE, related_name="retroalimentaciones",
                                  db_column="id_contenido")
    profesional = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="retroalimentaciones_ia",
                                    db_column="id_profesional")
    motivo = models.CharField("motivo", max_length=12, choices=MOTIVOS)
    comentario = models.TextField("comentario", validators=[validar_texto_minimo(10)])
    fecha_hora = models.DateTimeField("fecha y hora", default=timezone.now)

    class Meta:
        db_table = "retroalimentacion_ia"
        ordering = ["-fecha_hora"]
        verbose_name = "retroalimentación de IA"
        verbose_name_plural = "retroalimentaciones de IA"
