"""Evaluación diagnóstica integral (Decreto 170), planes de apoyo, avisos de reevaluación e informes (RF-05 a RF-08)."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.campos import TextoCifrado
from apps.core.validadores import sumar_anios, validar_no_futuro


class EvaluacionDiagnostica(models.Model):
    TIPOS = [("ingreso", "Ingreso"), ("reevaluacion", "Reevaluación")]
    ESTADOS = [("en_proceso", "En proceso"), ("cerrada", "Cerrada")]

    id = models.BigAutoField(primary_key=True, db_column="id_evaluacion")
    caso = models.ForeignKey("casos.Caso", on_delete=models.CASCADE, related_name="evaluaciones", db_column="id_caso")
    tipo_evaluacion = models.CharField("tipo de evaluación", max_length=12, choices=TIPOS, default="ingreso")
    tipo_nee = TextoCifrado("tipo de NEE", max_length=80)                # dato de salud (Ley 21.719): se guarda cifrado
    diagnostico = TextoCifrado("diagnóstico integral", blank=True)
    fecha_evaluacion = models.DateField("fecha de evaluación", validators=[validar_no_futuro])
    fecha_reevaluacion = models.DateField("fecha de reevaluación", null=True, blank=True,
                                          help_text="Si la NEE es transitoria se calcula a 2 años cuando se deja vacía.")
    estado = models.CharField("estado", max_length=12, choices=ESTADOS, default="en_proceso")

    class Meta:
        db_table = "evaluacion_diagnostica"
        ordering = ["-fecha_evaluacion"]
        verbose_name = "evaluación diagnóstica"
        verbose_name_plural = "evaluaciones diagnósticas"
        constraints = [
            models.CheckConstraint(
                condition=Q(fecha_reevaluacion__isnull=True) | Q(fecha_reevaluacion__gt=models.F("fecha_evaluacion")),
                name="ck_evaluacion_reevaluacion"),
        ]

    def __str__(self):
        return "Evaluación %s de %s (%s)" % (self.get_tipo_evaluacion_display().lower(), self.caso.estudiante,
                                             self.fecha_evaluacion.strftime("%d-%m-%Y"))

    @property
    def estudiante(self):
        return self.caso.estudiante

    def clean(self):
        errores = {}
        if self.caso_id:
            if self.caso.tipo_proceso not in ("pie_nee", "tea"):
                errores["caso"] = "La evaluación diagnóstica integral solo aplica a casos PIE/NEE o TEA."
            if self.fecha_evaluacion and self.fecha_evaluacion < self.caso.fecha_apertura:
                errores["fecha_evaluacion"] = "La evaluación no puede ser anterior a la apertura del caso."
            if self.fecha_evaluacion and not self.fecha_reevaluacion and \
                    self.caso.estudiante.necesidad_educativa == "transitoria":
                self.fecha_reevaluacion = sumar_anios(self.fecha_evaluacion, settings.REEVALUACION_ANIOS_TRANSITORIA)
        if self.fecha_reevaluacion and self.fecha_evaluacion and self.fecha_reevaluacion <= self.fecha_evaluacion:
            errores["fecha_reevaluacion"] = "La reevaluación debe ser posterior a la evaluación."
        if self.estado == "cerrada":
            if not (self.diagnostico or "").strip():
                errores["diagnostico"] = "Para cerrar la evaluación registre el diagnóstico integral."
            if self.pk and not self.participaciones.exists():
                errores["estado"] = "Registre al menos un profesional participante antes de cerrar la evaluación."
        if errores:
            raise ValidationError(errores)


class ParticipacionEvaluacion(models.Model):
    evaluacion = models.ForeignKey(EvaluacionDiagnostica, on_delete=models.CASCADE, related_name="participaciones",
                                   db_column="id_evaluacion")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="participaciones",
                                db_column="id_usuario")
    rol_profesional = models.CharField("rol profesional", max_length=40,
                                       help_text="Por ejemplo: psicóloga, educadora diferencial, fonoaudióloga.")
    aporte = TextoCifrado("aporte a la evaluación")
    fecha = models.DateField("fecha", default=timezone.localdate, validators=[validar_no_futuro])

    class Meta:
        db_table = "participacion_evaluacion"
        constraints = [models.UniqueConstraint(fields=["evaluacion", "usuario"], name="uq_participacion")]

    def clean(self):
        if self.evaluacion_id:
            if self.evaluacion.estado == "cerrada":
                raise ValidationError("La evaluación está cerrada.")
            if self.usuario_id and ParticipacionEvaluacion.objects.filter(
                    evaluacion_id=self.evaluacion_id, usuario_id=self.usuario_id).exclude(pk=self.pk).exists():
                raise ValidationError({"usuario": "Este profesional ya registró su participación."})
            if self.fecha and self.fecha < self.evaluacion.caso.fecha_apertura:
                raise ValidationError({"fecha": "La fecha no puede ser anterior a la apertura del caso."})


class PlanApoyo(models.Model):
    TIPOS = [("paci", "PACI"), ("pai", "PAI"), ("d67", "Plan del Decreto 67")]
    ESTADOS = [("vigente", "Vigente"), ("cerrado", "Cerrado")]

    id = models.BigAutoField(primary_key=True, db_column="id_plan")
    estudiante = models.ForeignKey("estudiantes.Estudiante", on_delete=models.CASCADE, related_name="planes",
                                   db_column="id_estudiante")
    evaluacion = models.ForeignKey(EvaluacionDiagnostica, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="planes", db_column="id_evaluacion")
    tipo = models.CharField("tipo", max_length=4, choices=TIPOS)
    adecuaciones = TextoCifrado("adecuaciones para el aula",
                                help_text="Visible para el profesor jefe. No incluya información clínica.")
    detalle = TextoCifrado("detalle del plan", blank=True)
    fecha_inicio = models.DateField("fecha de inicio")
    fecha_termino = models.DateField("fecha de término", null=True, blank=True)
    estado = models.CharField("estado", max_length=8, choices=ESTADOS, default="vigente")

    class Meta:
        db_table = "plan_apoyo"
        ordering = ["-fecha_inicio"]
        verbose_name = "plan de apoyo"
        verbose_name_plural = "planes de apoyo"
        constraints = [
            models.CheckConstraint(condition=Q(fecha_termino__isnull=True) | Q(fecha_termino__gte=models.F("fecha_inicio")),
                                   name="ck_plan_fechas"),
        ]

    def __str__(self):
        return "%s de %s" % (self.get_tipo_display(), self.estudiante)

    def clean(self):
        errores = {}
        if self.fecha_termino and self.fecha_inicio and self.fecha_termino < self.fecha_inicio:
            errores["fecha_termino"] = "La fecha de término no puede ser anterior a la de inicio."
        if self.evaluacion_id and self.estudiante_id and self.evaluacion.caso.estudiante_id != self.estudiante_id:
            errores["evaluacion"] = "La evaluación seleccionada no corresponde a este estudiante."
        if self.estado == "vigente" and self.estudiante_id and self.tipo:
            if PlanApoyo.objects.filter(estudiante_id=self.estudiante_id, tipo=self.tipo, estado="vigente").exclude(
                    pk=self.pk).exists():
                errores["tipo"] = "El estudiante ya tiene un plan vigente de este tipo. Ciérrelo antes de crear otro."
        if self.estado == "cerrado" and not self.fecha_termino:
            errores["fecha_termino"] = "Indique la fecha de término para cerrar el plan."
        if errores:
            raise ValidationError(errores)


class AvisoReevaluacion(models.Model):
    ESTADOS = [("pendiente", "Pendiente"), ("enviado", "Enviado"), ("atendido", "Atendido")]

    id = models.BigAutoField(primary_key=True, db_column="id_aviso")
    evaluacion = models.ForeignKey(EvaluacionDiagnostica, on_delete=models.CASCADE, related_name="avisos",
                                   db_column="id_evaluacion")
    destinatario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="avisos_reevaluacion",
                                     db_column="id_destinatario")
    fecha_programada = models.DateField("fecha programada")
    fecha_envio = models.DateTimeField("fecha de envío", null=True, blank=True)
    estado = models.CharField("estado", max_length=10, choices=ESTADOS, default="pendiente")

    class Meta:
        db_table = "aviso_reevaluacion"
        ordering = ["fecha_programada"]
        constraints = [models.UniqueConstraint(fields=["evaluacion", "destinatario"], name="uq_aviso_destinatario")]


class Informe(models.Model):
    TIPOS = [("preliminar_fudei", "Versión preliminar FUDEI"), ("familia", "Informe para la Familia"),
             ("seguimiento", "Informe de seguimiento")]
    ESTADOS = [("borrador", "Borrador"), ("validado", "Validado"), ("entregado", "Entregado en reunión presencial")]

    id = models.BigAutoField(primary_key=True, db_column="id_informe")
    caso = models.ForeignKey("casos.Caso", on_delete=models.CASCADE, related_name="informes", db_column="id_caso")
    tipo = models.CharField("tipo", max_length=20, choices=TIPOS)
    contenido = TextoCifrado("contenido")
    estado = models.CharField("estado", max_length=10, choices=ESTADOS, default="borrador")
    fecha_entrega = models.DateField("fecha de entrega", null=True, blank=True, validators=[validar_no_futuro])
    contenido_ia = models.OneToOneField("ia.ContenidoIA", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="informe", db_column="id_contenido_ia")

    class Meta:
        db_table = "informe"
        ordering = ["-id"]

    def __str__(self):
        return "%s — %s" % (self.get_tipo_display(), self.caso.estudiante)

    def clean(self):
        errores = {}
        if self.contenido_ia_id and self.caso_id and self.contenido_ia.caso_id != self.caso_id:
            errores["contenido_ia"] = "El borrador de IA pertenece a otro caso."
        if self.estado in ("validado", "entregado"):
            if not (self.contenido or "").strip():
                errores["contenido"] = "El informe no tiene contenido."
            if "[VERIFICAR" in (self.contenido or "").upper():
                errores["contenido"] = "El texto aún tiene marcas [VERIFICAR]; revíselas antes de validar."
            if self.contenido_ia_id and self.contenido_ia.estado != "validado":
                errores["estado"] = ("El informe usa un borrador del módulo de IA que aún no tiene validación humana "
                                     "(RF-18).")
        if self.estado == "entregado" and not self.fecha_entrega:
            errores["fecha_entrega"] = "Indique la fecha en que se entregó el informe en la reunión."
        if self.fecha_entrega and self.estado != "entregado":
            errores["fecha_entrega"] = "La fecha de entrega solo se registra cuando el informe fue entregado."
        if self.fecha_entrega and self.caso_id and self.fecha_entrega < self.caso.fecha_apertura:
            errores["fecha_entrega"] = "La fecha de entrega no puede ser anterior a la apertura del caso."
        if errores:
            raise ValidationError(errores)
