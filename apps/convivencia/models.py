"""Convivencia escolar (pantallas «Convivencia», «Protocolos» y «Plan de gestión» del prototipo v1).

- Conflictos y mediaciones.
- Anotaciones (positivas y faltas moderadas, graves o gravísimas, según el reglamento interno).
- Situación conductual (registros conductuales, académicos, de asistencia y atrasos).
- Protocolos de actuación activados (los ocho que exige el Ministerio y recoge el reglamento interno).
- Plan de gestión de convivencia escolar: actividades y sus medios de verificación.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.campos import TextoCifrado
from apps.core.validadores import validar_fecha_razonable, validar_no_futuro, validar_texto_minimo


def _no_futuro_ni_antiguo(fecha):
    validar_no_futuro(fecha)
    validar_fecha_razonable(fecha)


class Conflicto(models.Model):
    TIPOS = [("mediacion", "Mediación"), ("negociacion", "Negociación asistida"), ("arbitraje", "Arbitraje pedagógico"),
             ("dialogo", "Diálogo formativo"), ("otro", "Otra gestión")]
    RESULTADOS = [("en_proceso", "En proceso"), ("con_acuerdo", "Con acuerdo"), ("sin_acuerdo", "Sin acuerdo")]

    id = models.BigAutoField(primary_key=True, db_column="id_conflicto")
    fecha = models.DateField("fecha", default=timezone.localdate, validators=[_no_futuro_ni_antiguo])
    tipo_gestion = models.CharField("tipo de gestión", max_length=12, choices=TIPOS, default="mediacion")
    curso = models.ForeignKey("estudiantes.Curso", on_delete=models.PROTECT, related_name="conflictos",
                              db_column="id_curso")
    participantes = models.ManyToManyField("estudiantes.Estudiante", related_name="conflictos",
                                           db_table="conflicto_participante", verbose_name="estudiantes participantes")
    encargada = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="conflictos",
                                  db_column="id_encargada", verbose_name="encargada")
    descripcion = TextoCifrado("descripción del conflicto", validators=[validar_texto_minimo(20)])
    acuerdos = TextoCifrado("acuerdos", blank=True)
    resultado = models.CharField("resultado", max_length=12, choices=RESULTADOS, default="en_proceso")
    registrado_en = models.DateTimeField("registrado el", default=timezone.now, editable=False)

    class Meta:
        db_table = "conflicto"
        ordering = ["-fecha", "-id"]
        verbose_name = "conflicto"

    def __str__(self):
        return "%s · %s · %s" % (self.fecha.strftime("%d-%m-%Y"), self.get_tipo_gestion_display(), self.curso.nombre)

    def clean(self):
        if self.resultado == "con_acuerdo" and not (self.acuerdos or "").strip():
            raise ValidationError({"acuerdos": "Registre los acuerdos alcanzados."})


class Anotacion(models.Model):
    TIPOS = [("positiva", "Positiva"), ("moderada", "Falta moderada"), ("grave", "Falta grave"),
             ("gravisima", "Falta gravísima")]

    id = models.BigAutoField(primary_key=True, db_column="id_anotacion")
    estudiante = models.ForeignKey("estudiantes.Estudiante", on_delete=models.CASCADE, related_name="anotaciones",
                                   db_column="id_estudiante")
    fecha = models.DateField("fecha", default=timezone.localdate, validators=[_no_futuro_ni_antiguo])
    tipo = models.CharField("tipo", max_length=10, choices=TIPOS)
    descripcion = models.TextField("descripción", validators=[validar_texto_minimo(10)])
    registrada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="anotaciones",
                                       db_column="id_registrada_por")
    registrada_en = models.DateTimeField("registrada el", default=timezone.now, editable=False)

    class Meta:
        db_table = "anotacion"
        ordering = ["-fecha", "-id"]
        verbose_name = "anotación"
        verbose_name_plural = "anotaciones"

    def __str__(self):
        return "%s · %s" % (self.get_tipo_display(), self.estudiante)

    def clean(self):
        if self.estudiante_id and self.fecha and not self.estudiante.activo:
            raise ValidationError({"estudiante": "El estudiante no está activo."})


class RegistroConductual(models.Model):
    CATEGORIAS = [("conductual", "Conductual"), ("academica", "Académica"), ("asistencia", "Asistencia"),
                  ("atrasos", "Atrasos")]

    id = models.BigAutoField(primary_key=True, db_column="id_registro")
    estudiante = models.ForeignKey("estudiantes.Estudiante", on_delete=models.CASCADE,
                                   related_name="registros_conductuales", db_column="id_estudiante")
    fecha = models.DateField("fecha", default=timezone.localdate, validators=[_no_futuro_ni_antiguo])
    categoria = models.CharField("categoría", max_length=10, choices=CATEGORIAS)
    descripcion = models.TextField("descripción", validators=[validar_texto_minimo(10)])
    porcentaje_asistencia = models.DecimalField(
        "porcentaje de asistencia", max_digits=5, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Solo para asistencia. El reglamento considera inasistencia grave entre 50 % y 84 %.")
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                       related_name="registros_conductuales", db_column="id_registrado_por")
    registrado_en = models.DateTimeField("registrado el", default=timezone.now, editable=False)

    class Meta:
        db_table = "registro_conductual"
        ordering = ["-fecha", "-id"]
        verbose_name = "registro de situación conductual"
        verbose_name_plural = "situación conductual"
        constraints = [models.CheckConstraint(
            condition=Q(porcentaje_asistencia__isnull=True) | (Q(porcentaje_asistencia__gte=0) & Q(porcentaje_asistencia__lte=100)),
            name="ck_registro_asistencia")]

    def clean(self):
        if self.porcentaje_asistencia is not None and self.categoria != "asistencia":
            raise ValidationError({"porcentaje_asistencia": "El porcentaje solo aplica a registros de asistencia."})
        if self.categoria == "asistencia" and self.porcentaje_asistencia is None:
            raise ValidationError({"porcentaje_asistencia": "Indique el porcentaje de asistencia del estudiante."})
        if self.estudiante_id and not self.estudiante.activo:
            raise ValidationError({"estudiante": "El estudiante no está activo."})


class ProtocoloActivado(models.Model):
    # Protocolos que exige el Ministerio de Educación y recoge el reglamento interno del colegio.
    PROTOCOLOS = [
        ("vulneracion", "Frente a vulneración de derechos de los estudiantes"),
        ("abuso_sexual", "Frente a abusos, agresiones sexuales y hechos de connotación sexual"),
        ("alcohol_drogas", "Situaciones de alcohol y drogas"),
        ("violencia", "Violencia y/o maltrato entre miembros de la comunidad"),
        ("conducta_suicida", "Prevención de la conducta suicida y protocolo de actuación"),
        ("retencion_embarazo", "Retención y apoyo a estudiantes padres, madres y embarazadas"),
        ("salida_pedagogica", "Salidas pedagógicas"),
        ("accidente_escolar", "Accidentes escolares"),
    ]
    # Tipo de situación de una alerta de riesgo -> protocolo que activa.
    DESDE_ALERTA = {"vulneracion_derechos": "vulneracion", "abuso_sexual": "abuso_sexual",
                    "alcohol_drogas_armas": "alcohol_drogas", "violencia_maltrato": "violencia",
                    "conducta_suicida": "conducta_suicida"}
    ESTADOS = [("abierto", "Abierto"), ("cerrado", "Cerrado")]

    id = models.BigAutoField(primary_key=True, db_column="id_protocolo")
    protocolo = models.CharField("protocolo", max_length=20, choices=PROTOCOLOS)
    fecha_activacion = models.DateField("fecha de activación", default=timezone.localdate,
                                        validators=[_no_futuro_ni_antiguo])
    curso = models.ForeignKey("estudiantes.Curso", on_delete=models.PROTECT, related_name="protocolos",
                              db_column="id_curso")
    estudiante = models.ForeignKey("estudiantes.Estudiante", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="protocolos", db_column="id_estudiante",
                                   help_text="Opcional: algunos protocolos (salidas, accidentes) involucran al curso.")
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="protocolos",
                                    db_column="id_responsable")
    alerta = models.ForeignKey("alertas.AlertaRiesgo", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="protocolos", db_column="id_alerta")
    estado = models.CharField("estado", max_length=8, choices=ESTADOS, default="abierto")
    fecha_cierre = models.DateField("fecha de cierre", null=True, blank=True, validators=[validar_no_futuro])
    observaciones = TextoCifrado("observaciones", blank=True)

    class Meta:
        db_table = "protocolo_activado"
        ordering = ["-fecha_activacion", "-id"]
        verbose_name = "protocolo activado"
        verbose_name_plural = "protocolos activados"
        constraints = [models.CheckConstraint(
            condition=Q(fecha_cierre__isnull=True) | Q(fecha_cierre__gte=models.F("fecha_activacion")),
            name="ck_protocolo_fechas")]

    def __str__(self):
        return "%s · %s" % (self.get_protocolo_display(), self.curso.nombre)

    def clean(self):
        errores = {}
        if self.estudiante_id and self.curso_id and self.estudiante.curso_id != self.curso_id:
            errores["estudiante"] = "El estudiante no pertenece al curso indicado."
        if self.estado == "cerrado":
            if not self.fecha_cierre:
                errores["fecha_cierre"] = "Indique la fecha de cierre."
            if len((self.observaciones or "").strip()) < 20:
                errores["observaciones"] = "Para cerrar, describa en al menos 20 caracteres las acciones realizadas."
        elif self.fecha_cierre:
            errores["fecha_cierre"] = "Solo un protocolo cerrado tiene fecha de cierre."
        if self.fecha_cierre and self.fecha_activacion and self.fecha_cierre < self.fecha_activacion:
            errores["fecha_cierre"] = "La fecha de cierre no puede ser anterior a la activación."
        if errores:
            raise ValidationError(errores)


class ActividadPlan(models.Model):
    TIPOS = [("actividad", "Actividad"), ("taller", "Taller"), ("capacitacion", "Capacitación"),
             ("campana", "Campaña"), ("reunion", "Reunión"), ("otro", "Otro")]
    ESTADOS = [("pendiente", "Pendiente"), ("realizada", "Realizada")]

    id = models.BigAutoField(primary_key=True, db_column="id_actividad")
    tipo = models.CharField("tipo", max_length=12, choices=TIPOS, default="actividad")
    titulo = models.CharField("título", max_length=160)
    fecha = models.DateField("fecha", validators=[validar_fecha_razonable])
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="actividades_plan",
                                    db_column="id_responsable")
    medio_verificacion = models.CharField("medio de verificación", max_length=160, blank=True,
                                          help_text="Por ejemplo: planificación, PPT y actividades, lista de asistencia.")
    descripcion = models.TextField("descripción", blank=True)
    estado = models.CharField("estado", max_length=10, choices=ESTADOS, default="pendiente")

    class Meta:
        db_table = "actividad_plan"
        ordering = ["-fecha", "-id"]
        verbose_name = "actividad del plan de gestión"
        verbose_name_plural = "plan de gestión"

    def __str__(self):
        return self.titulo

    def clean(self):
        errores = {}
        self.titulo = " ".join((self.titulo or "").split())
        if len(self.titulo) < 5:
            errores["titulo"] = "El título debe tener al menos 5 caracteres."
        if self.estado == "realizada":
            if self.fecha and self.fecha > timezone.localdate():
                errores["estado"] = "Una actividad con fecha futura no puede marcarse como realizada."
            if not self.medio_verificacion.strip():
                errores["medio_verificacion"] = "Indique el medio de verificación de la actividad realizada."
        if errores:
            raise ValidationError(errores)


class EvidenciaActividad(models.Model):
    id = models.BigAutoField(primary_key=True, db_column="id_evidencia")
    actividad = models.ForeignKey(ActividadPlan, on_delete=models.CASCADE, related_name="evidencias",
                                  db_column="id_actividad")
    nombre_archivo = models.CharField("nombre del archivo", max_length=160)
    ruta_objeto = models.CharField("ruta del objeto", max_length=255, unique=True, editable=False)
    hash_sha256 = models.CharField("huella SHA-256", max_length=64, editable=False)
    subida_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+",
                                   db_column="id_subida_por")
    fecha_carga = models.DateTimeField("fecha de carga", default=timezone.now, editable=False)

    class Meta:
        db_table = "evidencia_actividad"
        ordering = ["fecha_carga"]

    def __str__(self):
        return self.nombre_archivo
