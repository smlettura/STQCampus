"""Gestión de casos: derivación, caso, sesiones de seguimiento, hitos y documentos (RF-01 a RF-04)."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.campos import TextoCifrado
from apps.core.validadores import sumar_anios, validar_no_futuro, validar_texto_minimo


class Derivacion(models.Model):
    id = models.BigAutoField(primary_key=True, db_column="id_derivacion")
    estudiante = models.ForeignKey("estudiantes.Estudiante", on_delete=models.CASCADE, related_name="derivaciones",
                                   db_column="id_estudiante")
    derivante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="derivaciones_hechas",
                                  db_column="id_derivante")
    fecha_hora = models.DateTimeField("fecha y hora", default=timezone.now, validators=[validar_no_futuro])
    motivo = TextoCifrado("motivo de la derivación", validators=[validar_texto_minimo(20)])
    caso = models.ForeignKey("Caso", on_delete=models.SET_NULL, null=True, blank=True, related_name="derivaciones",
                             db_column="id_caso")

    class Meta:
        db_table = "derivacion"
        ordering = ["-fecha_hora"]
        verbose_name = "derivación"
        verbose_name_plural = "derivaciones"

    def __str__(self):
        return "Derivación de %s (%s)" % (self.estudiante, timezone.localtime(self.fecha_hora).strftime("%d-%m-%Y"))

    @property
    def pendiente(self):
        return self.caso_id is None

    def clean(self):
        if self.caso_id and self.estudiante_id and self.caso.estudiante_id != self.estudiante_id:
            raise ValidationError({"caso": "El caso no corresponde al estudiante derivado."})


class Caso(models.Model):
    TIPOS_PROCESO = [("pie_nee", "Evaluación PIE/NEE"), ("tea", "Diagnóstico TEA"),
                     ("seguimiento", "Seguimiento psicosocial")]
    ESTADOS = [("abierto", "Abierto"), ("seguimiento", "En seguimiento"), ("cerrado", "Cerrado")]

    id = models.BigAutoField(primary_key=True, db_column="id_caso")
    estudiante = models.ForeignKey("estudiantes.Estudiante", on_delete=models.CASCADE, related_name="casos",
                                   db_column="id_estudiante")
    tipo_proceso = models.CharField("tipo de proceso", max_length=12, choices=TIPOS_PROCESO)
    tipo_atencion = models.CharField("tipo de atención", max_length=40, blank=True,
                                     help_text="Mencionado en la entrevista (E07); catálogo por confirmar con el equipo.")
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="casos_a_cargo",
                                    db_column="id_responsable")
    estado = models.CharField("estado", max_length=12, choices=ESTADOS, default="abierto")
    fecha_apertura = models.DateField("fecha de apertura", default=timezone.localdate, validators=[validar_no_futuro])
    fecha_cierre = models.DateField("fecha de cierre", null=True, blank=True, validators=[validar_no_futuro])
    fecha_fin_retencion = models.DateField("fin del plazo de retención", null=True, blank=True, editable=False)

    class Meta:
        db_table = "caso"
        ordering = ["-fecha_apertura", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(fecha_cierre__isnull=True) | Q(fecha_cierre__gte=models.F("fecha_apertura")),
                                   name="ck_caso_fechas"),
        ]

    def __str__(self):
        return "Caso %d · %s · %s" % (self.pk or 0, self.estudiante, self.get_tipo_proceso_display())

    @property
    def cerrado(self):
        return self.estado == "cerrado"

    def clean(self):
        errores = {}
        if self.responsable_id and not self.responsable.tiene_rol("psicologa", "asistente_social", "coordinacion_pie"):
            errores["responsable"] = "El responsable debe pertenecer al equipo psicosocial o a la Coordinación PIE."
        if self.fecha_cierre and self.fecha_apertura and self.fecha_cierre < self.fecha_apertura:
            errores["fecha_cierre"] = "La fecha de cierre no puede ser anterior a la apertura."
        if self.estado == "cerrado" and not self.fecha_cierre:
            errores["fecha_cierre"] = "Indique la fecha de cierre."
        if self.estado != "cerrado" and self.estudiante_id and self.tipo_proceso:
            duplicado = Caso.objects.filter(estudiante_id=self.estudiante_id, tipo_proceso=self.tipo_proceso).exclude(
                estado="cerrado").exclude(pk=self.pk)
            if duplicado.exists():
                errores["tipo_proceso"] = "El estudiante ya tiene un caso abierto de este tipo."
        if errores:
            raise ValidationError(errores)

    def calcular_fin_retencion(self):
        """RNF-10: 15 años desde el cierre o desde el egreso del estudiante, lo que ocurra después."""
        base = self.fecha_cierre
        egreso = self.estudiante.fecha_egreso
        if egreso and (base is None or egreso > base):
            base = egreso
        return sumar_anios(base, settings.RETENCION_ANIOS) if base else None


class SesionSeguimiento(models.Model):
    """Atención psicosocial (sesión de seguimiento) de un caso. Pantalla «Registrar atención» del prototipo v1."""

    NIVELES = [("equipo", "Equipo psicosocial"), ("autora", "Solo la autora")]
    TIPOS = [("individual", "Individual"), ("grupal", "Grupal"), ("familiar", "Familiar")]
    URGENCIAS = [("baja", "Baja"), ("media", "Media"), ("alta", "Alta")]
    DURACIONES = [(15, "15 minutos"), (30, "30 minutos"), (45, "45 minutos"), (60, "60 minutos"), (90, "90 minutos"),
                  (120, "120 minutos")]
    MOTIVOS = [("regulacion_emocional", "Regulación emocional"), ("conducta", "Conducta en aula"),
               ("relaciones_pares", "Relaciones con pares"), ("rendimiento", "Rendimiento académico"),
               ("asistencia", "Asistencia"), ("familiar", "Situación familiar"), ("animo", "Ánimo o tristeza"),
               ("ansiedad", "Ansiedad o estrés"), ("convivencia", "Convivencia escolar"),
               ("orientacion", "Orientación vocacional"), ("seguimiento_pie", "Seguimiento PIE"), ("otro", "Otro")]
    DERIVANTES = [("profesor_jefe", "Profesor jefe"), ("docente", "Docente de asignatura"),
                  ("inspectoria", "Inspectoría"), ("convivencia", "Convivencia escolar"), ("pie", "Equipo PIE"),
                  ("direccion", "Dirección"), ("apoderado", "Apoderado"), ("estudiante", "El propio estudiante"),
                  ("externo", "Institución externa"), ("otro", "Otro")]
    ESTADOS = [("borrador", "Borrador"), ("registrada", "Registrada")]

    id = models.BigAutoField(primary_key=True, db_column="id_sesion")
    caso = models.ForeignKey(Caso, on_delete=models.CASCADE, related_name="sesiones", db_column="id_caso")
    profesional = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sesiones",
                                    db_column="id_profesional")
    fecha_hora = models.DateTimeField("fecha y hora de inicio", validators=[validar_no_futuro])
    duracion_minutos = models.PositiveSmallIntegerField("duración", choices=DURACIONES, default=45)
    tipo_atencion = models.CharField("tipo de atención", max_length=10, choices=TIPOS, default="individual")
    urgencia = models.CharField("nivel de urgencia", max_length=5, choices=URGENCIAS, default="baja")
    motivo = models.CharField("motivo de consulta", max_length=24, choices=MOTIVOS, default="otro")
    derivado_por = models.CharField("derivado por", max_length=16, choices=DERIVANTES, blank=True)
    nota = TextoCifrado("descripción de la sesión", blank=True)
    acuerdos = TextoCifrado("acuerdos y compromisos", blank=True)
    nivel_acceso = models.CharField("nivel de acceso", max_length=10, choices=NIVELES, default="equipo")
    estado = models.CharField("estado", max_length=10, choices=ESTADOS, default="registrada")

    class Meta:
        db_table = "sesion_seguimiento"
        ordering = ["fecha_hora"]
        verbose_name = "atención"
        verbose_name_plural = "atenciones"

    def __str__(self):
        return "%s · %s" % (timezone.localtime(self.fecha_hora).strftime("%d-%m-%Y"), self.get_tipo_atencion_display())

    @property
    def titulo(self):
        """Como en «Atenciones anteriores» del prototipo: «Sesión individual», «Sesión con apoderado»…"""
        return {"individual": "Sesión individual", "grupal": "Sesión grupal",
                "familiar": "Sesión con la familia"}[self.tipo_atencion]

    def clean(self):
        errores = {}
        if self.caso_id and self.fecha_hora:
            if self.caso.cerrado:
                raise ValidationError("No se pueden registrar atenciones en un caso cerrado.")
            if timezone.localtime(self.fecha_hora).date() < self.caso.fecha_apertura:
                errores["fecha_hora"] = "La atención no puede ser anterior a la apertura del caso."
        if self.estado == "registrada":
            if len((self.nota or "").strip()) < 10:
                errores["nota"] = "Describa la sesión con al menos 10 caracteres (o guárdela como borrador)."
        if errores:
            raise ValidationError(errores)

    def visible_para(self, usuario):
        return self.nivel_acceso == "equipo" or self.profesional_id == usuario.pk


class Hito(models.Model):
    TIPOS = [("objetivo", "Objetivo"), ("hallazgo", "Hallazgo"), ("logro", "Logro"),
             ("entrevista_apoderado", "Entrevista al apoderado"), ("observacion", "Observación")]

    id = models.BigAutoField(primary_key=True, db_column="id_hito")
    caso = models.ForeignKey(Caso, on_delete=models.CASCADE, related_name="hitos", db_column="id_caso")
    tipo = models.CharField("tipo", max_length=20, choices=TIPOS)
    descripcion = models.TextField("descripción", validators=[validar_texto_minimo(5)])
    fecha = models.DateField("fecha", default=timezone.localdate, validators=[validar_no_futuro])
    visible_profesor_jefe = models.BooleanField("visible para el profesor jefe", default=False)

    class Meta:
        db_table = "hito"
        ordering = ["fecha", "id"]

    def clean(self):
        if self.caso_id and self.fecha:
            if self.caso.cerrado:
                raise ValidationError("No se pueden registrar hitos en un caso cerrado.")
            if self.fecha < self.caso.fecha_apertura:
                raise ValidationError({"fecha": "El hito no puede ser anterior a la apertura del caso."})


class Documento(models.Model):
    TIPOS = [("informe_externo", "Informe externo"), ("certificado_medico", "Certificado médico"),
             ("evaluacion_externa", "Evaluación de otro profesional"), ("consentimiento", "Consentimiento firmado"),
             ("otro", "Otro")]

    id = models.BigAutoField(primary_key=True, db_column="id_documento")
    caso = models.ForeignKey(Caso, on_delete=models.CASCADE, related_name="documentos", db_column="id_caso")
    tipo = models.CharField("tipo", max_length=20, choices=TIPOS)
    nombre_archivo = models.CharField("nombre del archivo", max_length=160)
    ruta_objeto = models.CharField("ruta del objeto", max_length=255, unique=True, editable=False)
    hash_sha256 = models.CharField("huella SHA-256", max_length=64, editable=False)
    fecha_carga = models.DateTimeField("fecha de carga", default=timezone.now, editable=False)

    class Meta:
        db_table = "documento"
        ordering = ["-fecha_carga"]

    def __str__(self):
        return self.nombre_archivo
