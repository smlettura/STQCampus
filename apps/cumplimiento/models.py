"""Consentimiento informado (RF-11), derechos ARCO+ (RF-12) y retención de 15 años (RNF-10)."""
import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.validadores import validar_no_futuro


class Consentimiento(models.Model):
    ALCANCES = [
        ("evaluacion_pie", "Evaluación diagnóstica integral (PIE)"),
        ("seguimiento", "Seguimiento psicosocial"),
        ("uso_ia", "Uso del módulo de IA con datos seudonimizados (cuando esté disponible)"),
    ]

    id = models.BigAutoField(primary_key=True, db_column="id_consentimiento")
    estudiante = models.ForeignKey("estudiantes.Estudiante", on_delete=models.CASCADE, related_name="consentimientos",
                                   db_column="id_estudiante")
    apoderado = models.ForeignKey("estudiantes.Apoderado", on_delete=models.PROTECT, related_name="consentimientos",
                                  db_column="id_apoderado")
    alcance = models.CharField("alcance", max_length=160, choices=ALCANCES)
    fecha_otorgamiento = models.DateField("fecha de otorgamiento", validators=[validar_no_futuro])
    fecha_revocacion = models.DateField("fecha de revocación", null=True, blank=True, validators=[validar_no_futuro])
    documento = models.ForeignKey("casos.Documento", on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="consentimientos", db_column="id_documento",
                                  help_text="Copia escaneada del consentimiento firmado (opcional).")

    class Meta:
        db_table = "consentimiento"
        ordering = ["-fecha_otorgamiento"]
        constraints = [
            models.CheckConstraint(
                condition=Q(fecha_revocacion__isnull=True) | Q(fecha_revocacion__gte=models.F("fecha_otorgamiento")),
                name="ck_consentimiento_fechas"),
        ]

    def __str__(self):
        return "%s — %s" % (self.get_alcance_display(), self.estudiante)

    @property
    def vigente(self):
        return self.fecha_revocacion is None or self.fecha_revocacion > timezone.localdate()

    @classmethod
    def vigente_para(cls, estudiante, alcance):
        """Un tratamiento bloqueado por una solicitud ARCO+ (derecho de bloqueo) suspende todos los alcances."""
        if BloqueoTratamiento.activo_para(estudiante):
            return False
        hoy = timezone.localdate()
        return cls.objects.filter(estudiante=estudiante, alcance=alcance, fecha_otorgamiento__lte=hoy).filter(
            Q(fecha_revocacion__isnull=True) | Q(fecha_revocacion__gt=hoy)).exists()

    def clean(self):
        errores = {}
        if self.estudiante_id and self.apoderado_id:
            if not self.estudiante.vinculos_apoderado.filter(apoderado_id=self.apoderado_id).exists():
                errores["apoderado"] = "El apoderado no está vinculado a este estudiante."
        if self.fecha_revocacion and self.fecha_otorgamiento and self.fecha_revocacion < self.fecha_otorgamiento:
            errores["fecha_revocacion"] = "La revocación no puede ser anterior al otorgamiento."
        if self.documento_id and self.estudiante_id and self.documento.caso.estudiante_id != self.estudiante_id:
            errores["documento"] = "El documento pertenece a otro estudiante."
        if self.estudiante_id and self.alcance and self.fecha_revocacion is None:
            repetido = Consentimiento.objects.filter(estudiante_id=self.estudiante_id, alcance=self.alcance,
                                                     fecha_revocacion__isnull=True).exclude(pk=self.pk)
            if repetido.exists():
                errores["alcance"] = "Ya existe un consentimiento vigente con este alcance."
        if errores:
            raise ValidationError(errores)


class SolicitudARCO(models.Model):
    DERECHOS = [("acceso", "Acceso"), ("rectificacion", "Rectificación"), ("supresion", "Supresión (cancelación)"),
                ("oposicion", "Oposición"), ("portabilidad", "Portabilidad"), ("bloqueo", "Bloqueo")]
    ESTADOS = [("recibida", "Recibida"), ("en_analisis", "En análisis"), ("respondida", "Respondida"),
               ("rechazada", "Rechazada")]

    id = models.BigAutoField(primary_key=True, db_column="id_solicitud")
    estudiante = models.ForeignKey("estudiantes.Estudiante", on_delete=models.CASCADE, related_name="solicitudes_arco",
                                   db_column="id_estudiante")
    apoderado = models.ForeignKey("estudiantes.Apoderado", on_delete=models.PROTECT, related_name="solicitudes_arco",
                                  db_column="id_apoderado")
    tipo_derecho = models.CharField("derecho ejercido", max_length=14, choices=DERECHOS)
    fecha_recepcion = models.DateField("fecha de recepción", default=timezone.localdate, validators=[validar_no_futuro])
    fecha_limite = models.DateField("fecha límite de respuesta", editable=False)
    estado = models.CharField("estado", max_length=12, choices=ESTADOS, default="recibida")
    detalle = models.TextField("qué solicita el titular", blank=True,
                               help_text="Por ejemplo: qué dato corregir, a qué tratamiento se opone o qué desea suprimir.")
    respuesta = models.TextField("respuesta al titular", blank=True,
                                 help_text="Texto que recibirá el apoderado. Si se rechaza, indique el fundamento legal.")
    fecha_respuesta = models.DateField("fecha de respuesta", null=True, blank=True, validators=[validar_no_futuro])
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="solicitudes_arco",
                                    db_column="id_responsable")

    class Meta:
        db_table = "solicitud_arco"
        ordering = ["fecha_limite"]
        verbose_name = "solicitud ARCO+"
        verbose_name_plural = "solicitudes ARCO+"
        constraints = [
            models.CheckConstraint(condition=Q(fecha_limite__gte=models.F("fecha_recepcion")), name="ck_arco_limite"),
            models.CheckConstraint(
                condition=Q(fecha_respuesta__isnull=True) | Q(fecha_respuesta__gte=models.F("fecha_recepcion")),
                name="ck_arco_respuesta"),
        ]

    def __str__(self):
        return "%s — %s" % (self.get_tipo_derecho_display(), self.estudiante)

    @property
    def vencida(self):
        return self.estado in ("recibida", "en_analisis") and self.fecha_limite < timezone.localdate()

    def save(self, *args, **kwargs):
        if self.fecha_recepcion and not self.fecha_limite:
            self.fecha_limite = self.fecha_recepcion + datetime.timedelta(days=settings.ARCO_PLAZO_DIAS)
        super().save(*args, **kwargs)

    def clean(self):
        errores = {}
        if self.fecha_recepcion:
            self.fecha_limite = self.fecha_recepcion + datetime.timedelta(days=settings.ARCO_PLAZO_DIAS)
        if self.estudiante_id and self.apoderado_id and \
                not self.estudiante.vinculos_apoderado.filter(apoderado_id=self.apoderado_id).exists():
            errores["apoderado"] = "Solo un apoderado vinculado al estudiante puede ejercer estos derechos."
        if self.estado in ("respondida", "rechazada") and not self.fecha_respuesta:
            errores["fecha_respuesta"] = "Indique la fecha de respuesta."
        if self.estado in ("respondida", "rechazada") and not (self.respuesta or "").strip():
            errores["respuesta"] = "Escriba la respuesta que recibirá el titular."
        if self.fecha_respuesta and self.fecha_recepcion and self.fecha_respuesta < self.fecha_recepcion:
            errores["fecha_respuesta"] = "La respuesta no puede ser anterior a la recepción."
        if self.responsable_id and not self.responsable.tiene_permiso("arco.gestionar"):
            errores["responsable"] = "El responsable debe tener permiso para atender solicitudes ARCO+."
        if errores:
            raise ValidationError(errores)


class AccionARCO(models.Model):
    """Historial de lo que se hizo para atender una solicitud ARCO+. El detalle no guarda datos personales."""
    TIPOS = [("registro", "Registro de la solicitud"), ("analisis", "Inicio del análisis"),
             ("exportacion", "Exportación del expediente"), ("informe_acceso", "Informe de acceso generado"),
             ("rectificacion", "Rectificación aplicada"), ("supresion", "Supresión propuesta a la Dirección"),
             ("oposicion", "Oposición: consentimiento revocado"), ("bloqueo", "Tratamiento bloqueado"),
             ("desbloqueo", "Bloqueo levantado"), ("respuesta", "Respuesta registrada")]

    id = models.BigAutoField(primary_key=True, db_column="id_accion_arco")
    solicitud = models.ForeignKey(SolicitudARCO, on_delete=models.CASCADE, related_name="acciones", db_column="id_solicitud")
    fecha_hora = models.DateTimeField("fecha y hora", default=timezone.now)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="acciones_arco",
                                db_column="id_usuario")
    tipo = models.CharField("acción", max_length=16, choices=TIPOS)
    detalle = models.CharField("detalle", max_length=255, blank=True)

    class Meta:
        db_table = "accion_arco"
        ordering = ["fecha_hora", "id"]
        verbose_name = "acción ARCO+"
        verbose_name_plural = "acciones ARCO+"

    def __str__(self):
        return "%s (%s)" % (self.get_tipo_display(), self.fecha_hora)


class BloqueoTratamiento(models.Model):
    """Derecho de bloqueo: suspende temporalmente el tratamiento (copiloto de IA, nuevas evaluaciones con consentimiento)
    mientras se resuelve una solicitud. Los datos se conservan."""
    id = models.BigAutoField(primary_key=True, db_column="id_bloqueo")
    estudiante = models.ForeignKey("estudiantes.Estudiante", on_delete=models.CASCADE, related_name="bloqueos",
                                   db_column="id_estudiante")
    solicitud = models.ForeignKey(SolicitudARCO, on_delete=models.SET_NULL, null=True, blank=True, related_name="bloqueos",
                                  db_column="id_solicitud")
    motivo = models.CharField("motivo", max_length=255)
    fecha_inicio = models.DateTimeField("inicio", default=timezone.now)
    fecha_termino = models.DateTimeField("término", null=True, blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bloqueos_creados",
                                   db_column="id_creado_por")

    class Meta:
        db_table = "bloqueo_tratamiento"
        ordering = ["-fecha_inicio"]
        verbose_name = "bloqueo de tratamiento"
        verbose_name_plural = "bloqueos de tratamiento"

    def __str__(self):
        return "Bloqueo de %s" % self.estudiante

    @property
    def vigente(self):
        return self.fecha_termino is None

    @classmethod
    def activo_para(cls, estudiante):
        if estudiante is None or not getattr(estudiante, "pk", None):
            return False
        return cls.objects.filter(estudiante=estudiante, fecha_termino__isnull=True).exists()


class RetencionEliminacion(models.Model):
    ACCIONES = [("eliminar", "Eliminar"), ("anonimizar", "Anonimizar")]
    ESTADOS = [("propuesta", "Propuesta"), ("autorizada", "Autorizada"), ("postergada", "Postergada"),
               ("ejecutada", "Ejecutada")]

    id = models.BigAutoField(primary_key=True, db_column="id_retencion")
    estudiante = models.ForeignKey("estudiantes.Estudiante", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="retenciones", db_column="id_estudiante")
    fecha_vencimiento = models.DateField("fecha de vencimiento del plazo")
    accion = models.CharField("acción", max_length=10, choices=ACCIONES, default="anonimizar")
    estado = models.CharField("estado", max_length=10, choices=ESTADOS, default="propuesta")
    autorizada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                       related_name="retenciones_autorizadas", db_column="id_autorizada_por")
    fecha_autorizacion = models.DateTimeField("fecha de autorización", null=True, blank=True)
    fecha_ejecucion = models.DateTimeField("fecha de ejecución", null=True, blank=True)
    origen = models.CharField("origen", max_length=10, choices=[("retencion", "Plazo de retención cumplido"),
                                                               ("arco", "Solicitud de supresión ARCO+")],
                              default="retencion")
    solicitud_arco = models.ForeignKey(SolicitudARCO, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="supresiones", db_column="id_solicitud_arco")

    class Meta:
        db_table = "retencion_eliminacion"
        ordering = ["fecha_vencimiento"]
        verbose_name = "eliminación por retención"
        verbose_name_plural = "eliminaciones por retención"
        constraints = [
            # Nada se ejecuta sin una autorización registrada (reglamento interno y RNF-10).
            models.CheckConstraint(
                condition=~Q(estado__in=["autorizada", "ejecutada"]) |
                (Q(autorizada_por__isnull=False) & Q(fecha_autorizacion__isnull=False)),
                name="ck_retencion_autorizacion"),
        ]

    def __str__(self):
        return "Retención de %s (vence %s)" % (self.estudiante or "registro anonimizado", self.fecha_vencimiento)

    def clean(self):
        errores = {}
        if self.estado in ("autorizada", "ejecutada"):
            if not self.autorizada_por_id or not self.fecha_autorizacion:
                errores["estado"] = "La eliminación requiere la autorización registrada de la Directora."
            elif not self.autorizada_por.tiene_rol("directora"):
                errores["autorizada_por"] = "Solo la Directora puede autorizar la eliminación."
            if self.origen == "retencion" and self.fecha_vencimiento and self.fecha_vencimiento > timezone.localdate():
                errores["fecha_vencimiento"] = "El plazo de retención aún no se cumple."
        if errores:
            raise ValidationError(errores)
