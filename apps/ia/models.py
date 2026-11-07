"""Módulo de IA (DER-F): copiloto que redacta borradores con Gemma 2 9B en un equipo propio, configurado con un
Modelfile (sin reentrenamiento). La plataforma deja las solicitudes seudonimizadas en una cola (SolicitudIA) y el agente
del equipo propio las toma por HTTPS con su token (AgenteIA). Ver `apps/ia/servicios.py` y el Anexo G del informe.
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
               ("descartado", "Descartado"), ("bloqueado", "Bloqueado: se salió de los límites del módulo")]

    id = models.BigAutoField(primary_key=True, db_column="id_contenido")
    caso = models.ForeignKey("casos.Caso", on_delete=models.CASCADE, related_name="contenidos_ia", db_column="id_caso")
    solicitante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="contenidos_ia",
                                    db_column="id_solicitante")
    tipo = models.CharField("tipo", max_length=20, choices=TIPOS)
    modelo = models.CharField("modelo", max_length=60)
    texto_generado = TextoCifrado("texto generado")
    texto_validado = TextoCifrado("texto validado por la profesional", blank=True)
    alertas = TextoCifrado("avisos para la profesional", blank=True)   # uno por línea (marcadores, límites, cifras nuevas)
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
    comentario = TextoCifrado("comentario", validators=[validar_texto_minimo(10)])
    fecha_hora = models.DateTimeField("fecha y hora", default=timezone.now)

    class Meta:
        db_table = "retroalimentacion_ia"
        ordering = ["-fecha_hora"]
        verbose_name = "retroalimentación de IA"
        verbose_name_plural = "retroalimentaciones de IA"


class AgenteIA(models.Model):
    """Equipo propio que ejecuta el modelo. Solo se guarda el hash SHA-256 de su token (el valor se muestra una vez)."""
    id = models.BigAutoField(primary_key=True, db_column="id_agente")
    nombre = models.CharField("nombre", max_length=60, unique=True)
    hash_token = models.CharField("hash del token", max_length=64, unique=True)
    activo = models.BooleanField("activo", default=True)
    fecha_emision = models.DateTimeField("fecha de emisión del token", default=timezone.now)
    ultimo_latido = models.DateTimeField("último latido", null=True, blank=True)
    modelo = models.CharField("modelo informado por el agente", max_length=60, blank=True)

    class Meta:
        db_table = "agente_ia"
        verbose_name = "agente de IA"
        verbose_name_plural = "agentes de IA"

    def __str__(self):
        return self.nombre


class SolicitudIA(models.Model):
    """Cola de solicitudes del copiloto. El texto seudonimizado y la tabla de correspondencia quedan cifrados y se borran
    cuando la profesional valida o descarta el borrador, o cuando la solicitud expira (sección 9.1.6 del informe)."""
    ESTADOS = [("pendiente", "Pendiente"), ("en_proceso", "En proceso"), ("lista", "Lista"), ("error", "Error"),
               ("expirada", "Expirada"), ("cerrada", "Cerrada")]

    id = models.BigAutoField(primary_key=True, db_column="id_solicitud")
    caso = models.ForeignKey("casos.Caso", on_delete=models.CASCADE, related_name="solicitudes_ia", db_column="id_caso")
    solicitante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="solicitudes_ia",
                                    db_column="id_solicitante")
    tipo_informe = models.CharField("tipo de informe", max_length=20)
    secciones = models.CharField("secciones", max_length=120)
    texto_seudonimizado = TextoCifrado("texto seudonimizado", blank=True)
    correspondencia = TextoCifrado("tabla de correspondencia", blank=True)
    hash_entrada = models.CharField("hash del texto seudonimizado", max_length=64)
    estado = models.CharField("estado", max_length=12, choices=ESTADOS, default="pendiente")
    intentos = models.PositiveSmallIntegerField("intentos", default=0)
    agente = models.ForeignKey(AgenteIA, on_delete=models.SET_NULL, null=True, blank=True, related_name="solicitudes",
                               db_column="id_agente")
    fecha_creacion = models.DateTimeField("fecha de creación", default=timezone.now)
    fecha_toma = models.DateTimeField("fecha en que el agente la tomó", null=True, blank=True)
    fecha_termino = models.DateTimeField("fecha de término", null=True, blank=True)
    contenido = models.OneToOneField(ContenidoIA, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="solicitud", db_column="id_contenido")
    detalle_error = models.CharField("detalle del error", max_length=200, blank=True)
    avisos = TextoCifrado("avisos de la entrada", blank=True)       # indicaciones ignoradas, órdenes neutralizadas
    reintentado = models.BooleanField("ya tuvo el reintento correctivo", default=False)

    class Meta:
        db_table = "solicitud_ia"
        ordering = ["-fecha_creacion"]
        verbose_name = "solicitud al copiloto"
        verbose_name_plural = "solicitudes al copiloto"
        indexes = [models.Index(fields=["estado", "fecha_creacion"], name="ix_solicitud_ia_estado")]
