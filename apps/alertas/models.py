"""Alertas de riesgo, enrutamiento según el reglamento interno, constancias y denuncia (RF-13, RF-14)."""
import datetime
import hashlib

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.campos import TextoCifrado
from apps.core.validadores import validar_no_futuro, validar_texto_minimo

TIPOS_SITUACION = [
    ("vulneracion_derechos", "Vulneración de derechos hacia estudiantes"),
    ("abuso_sexual", "Abuso, agresión sexual o hechos de connotación sexual"),
    ("alcohol_drogas_armas", "Situaciones de alcohol, drogas y armas"),
    ("conducta_suicida", "Riesgo de conducta suicida"),
    ("violencia_maltrato", "Violencia o maltrato entre miembros de la comunidad"),
]
SUBTIPOS_VIOLENCIA = [
    ("entre_adultos", "Entre adultos de la comunidad"),
    ("entre_estudiantes", "Entre estudiantes"),
    ("estudiante_a_adulto", "De un estudiante a un adulto"),
    ("adulto_a_estudiante", "De un adulto a un estudiante"),
]


def _hash(*partes):
    return hashlib.sha256("|".join(str(p) for p in partes).encode("utf-8")).hexdigest()


def _utc(valor):
    """Representación estable de una fecha y hora para las constancias, independiente de la zona horaria."""
    return valor.astimezone(datetime.timezone.utc).isoformat(timespec="microseconds")


class ReglaEnrutamiento(models.Model):
    """Carga la tabla «¿A quién reportar?» del reglamento interno. Sede vacía = todas las sedes."""

    id = models.BigAutoField(primary_key=True, db_column="id_regla")
    tipo_situacion = models.CharField("tipo de situación", max_length=24, choices=TIPOS_SITUACION)
    subtipo_violencia = models.CharField("subtipo de violencia", max_length=24, choices=SUBTIPOS_VIOLENCIA, blank=True)
    sede = models.ForeignKey("core.Sede", on_delete=models.PROTECT, null=True, blank=True, related_name="reglas",
                             db_column="id_sede")
    rol_responsable = models.ForeignKey("cuentas.Rol", on_delete=models.PROTECT, related_name="reglas",
                                        db_column="id_rol_responsable")
    vigente = models.BooleanField("vigente", default=True)

    class Meta:
        db_table = "regla_enrutamiento"
        ordering = ["tipo_situacion", "subtipo_violencia", "sede__nombre"]
        verbose_name = "regla de enrutamiento"
        verbose_name_plural = "reglas de enrutamiento"
        constraints = [models.UniqueConstraint(fields=["tipo_situacion", "subtipo_violencia", "sede", "rol_responsable"],
                                               name="uq_regla_enrutamiento")]

    def __str__(self):
        return "%s%s → %s (%s)" % (self.get_tipo_situacion_display(),
                                   " / " + self.get_subtipo_violencia_display() if self.subtipo_violencia else "",
                                   self.rol_responsable, self.sede or "todas las sedes")

    def clean(self):
        if self.tipo_situacion == "violencia_maltrato" and not self.subtipo_violencia:
            raise ValidationError({"subtipo_violencia": "Indique el subtipo de violencia."})
        if self.tipo_situacion != "violencia_maltrato" and self.subtipo_violencia:
            raise ValidationError({"subtipo_violencia": "El subtipo solo aplica a violencia o maltrato."})


class AlertaRiesgo(models.Model):
    ESTADOS = [("registrada", "Registrada"), ("en_gestion", "En gestión"), ("denunciada", "Denunciada"),
               ("cerrada", "Cerrada")]

    id = models.BigAutoField(primary_key=True, db_column="id_alerta")
    estudiante = models.ForeignKey("estudiantes.Estudiante", on_delete=models.CASCADE, related_name="alertas",
                                   db_column="id_estudiante")
    caso = models.ForeignKey("casos.Caso", on_delete=models.SET_NULL, null=True, blank=True, related_name="alertas",
                             db_column="id_caso")
    sede = models.ForeignKey("core.Sede", on_delete=models.PROTECT, related_name="alertas", db_column="id_sede")
    tipo_situacion = models.CharField("tipo de situación", max_length=24, choices=TIPOS_SITUACION)
    subtipo_violencia = models.CharField("subtipo de violencia", max_length=24, choices=SUBTIPOS_VIOLENCIA, blank=True)
    descripcion = TextoCifrado("descripción de lo observado", validators=[validar_texto_minimo(20)])
    fecha_hora_conocimiento = models.DateTimeField("fecha y hora en que tomó conocimiento", validators=[validar_no_futuro])
    fecha_hora_registro = models.DateTimeField("fecha y hora de registro", default=timezone.now, editable=False)
    posible_delito = models.BooleanField("podría constituir delito", default=False)
    estado = models.CharField("estado", max_length=12, choices=ESTADOS, default="registrada")
    informante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="alertas_informadas",
                                   db_column="id_informante")

    class Meta:
        db_table = "alerta_riesgo"
        ordering = ["-fecha_hora_registro"]
        verbose_name = "alerta de riesgo"
        verbose_name_plural = "alertas de riesgo"
        constraints = [
            models.CheckConstraint(condition=Q(fecha_hora_conocimiento__lte=models.F("fecha_hora_registro")),
                                   name="ck_alerta_conocimiento"),
        ]

    def __str__(self):
        return "Alerta %d · %s" % (self.pk or 0, self.get_tipo_situacion_display())

    @property
    def plazo_denuncia(self):
        return self.fecha_hora_conocimiento + datetime.timedelta(hours=settings.PLAZO_DENUNCIA_HORAS)

    def clean(self):
        errores = {}
        if self.tipo_situacion == "violencia_maltrato" and not self.subtipo_violencia:
            errores["subtipo_violencia"] = "Indique entre quiénes ocurrió la violencia o el maltrato."
        if self.tipo_situacion and self.tipo_situacion != "violencia_maltrato" and self.subtipo_violencia:
            errores["subtipo_violencia"] = "El subtipo solo aplica a violencia o maltrato."
        if self.caso_id and self.estudiante_id and self.caso.estudiante_id != self.estudiante_id:
            errores["caso"] = "El caso no corresponde al estudiante."
        referencia = self.fecha_hora_registro or timezone.now()
        if self.fecha_hora_conocimiento and self.fecha_hora_conocimiento > referencia + datetime.timedelta(minutes=5):
            errores["fecha_hora_conocimiento"] = "No puede ser posterior al registro de la alerta."
        if self.fecha_hora_conocimiento and self.fecha_hora_conocimiento < referencia - datetime.timedelta(days=365):
            errores["fecha_hora_conocimiento"] = "La fecha de conocimiento tiene más de un año; revise el dato."
        if errores:
            raise ValidationError(errores)


class Notificacion(models.Model):
    CANALES = [("correo", "Correo"), ("plataforma", "Aviso en la plataforma")]

    id = models.BigAutoField(primary_key=True, db_column="id_notificacion")
    alerta = models.ForeignKey(AlertaRiesgo, on_delete=models.CASCADE, related_name="notificaciones", db_column="id_alerta")
    destinatario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="notificaciones",
                                     db_column="id_destinatario")
    canal = models.CharField("canal", max_length=10, choices=CANALES, default="plataforma")
    fecha_hora_envio = models.DateTimeField("fecha y hora de envío", default=timezone.now)
    fecha_hora_lectura = models.DateTimeField("fecha y hora de lectura", null=True, blank=True)
    hash_constancia = models.CharField("hash de la constancia", max_length=64, unique=True)

    class Meta:
        db_table = "notificacion"
        ordering = ["-fecha_hora_envio"]
        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"

    def calcular_hash(self):
        return _hash("notificacion", self.alerta_id, self.destinatario_id, self.canal,
                     _utc(self.fecha_hora_envio), self.alerta.tipo_situacion)

    def constancia_integra(self):
        return self.calcular_hash() == self.hash_constancia


class GestionAlerta(models.Model):
    ACCIONES = [("protocolo_activado", "Protocolo activado"), ("entrevista", "Entrevista"),
                ("medida_resguardo", "Medida de resguardo"), ("derivacion_externa", "Derivación externa"),
                ("cierre", "Cierre")]

    id = models.BigAutoField(primary_key=True, db_column="id_gestion")
    alerta = models.ForeignKey(AlertaRiesgo, on_delete=models.CASCADE, related_name="gestiones", db_column="id_alerta")
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="gestiones_alerta",
                                    db_column="id_responsable")
    accion = models.CharField("acción", max_length=20, choices=ACCIONES)
    detalle = TextoCifrado("detalle", validators=[validar_texto_minimo(10)])
    fecha_hora = models.DateTimeField("fecha y hora", default=timezone.now, validators=[validar_no_futuro])

    class Meta:
        db_table = "gestion_alerta"
        ordering = ["fecha_hora"]
        verbose_name = "gestión de la alerta"
        verbose_name_plural = "gestiones de la alerta"

    def clean(self):
        errores = {}
        if self.alerta_id:
            alerta = self.alerta
            if alerta.estado == "cerrada":
                errores["accion"] = "La alerta ya está cerrada."
            if self.fecha_hora and self.fecha_hora < alerta.fecha_hora_conocimiento:
                errores["fecha_hora"] = "La gestión no puede ser anterior al conocimiento de la situación."
            if self.accion == "cierre":
                motivos = []
                if not alerta.gestiones.filter(accion="protocolo_activado").exists():
                    motivos.append("Antes de cerrar, registre la activación del protocolo del reglamento.")
                if alerta.posible_delito and not Denuncia.objects.filter(alerta=alerta).exists():
                    motivos.append("La situación podría constituir delito: no se puede cerrar sin la denuncia registrada.")
                if motivos:
                    errores["accion"] = motivos
        if errores:
            raise ValidationError(errores)


class Denuncia(models.Model):
    INSTITUCIONES = [("ministerio_publico", "Ministerio Público (Fiscalía)"), ("carabineros", "Carabineros de Chile"),
                     ("pdi", "Policía de Investigaciones")]

    id = models.BigAutoField(primary_key=True, db_column="id_denuncia")
    alerta = models.OneToOneField(AlertaRiesgo, on_delete=models.CASCADE, related_name="denuncia", db_column="id_alerta")
    psicologa = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="denuncias",
                                  db_column="id_psicologa")
    institucion = models.CharField("institución", max_length=20, choices=INSTITUCIONES)
    fecha_hora_presentacion = models.DateTimeField("fecha y hora de presentación", validators=[validar_no_futuro])
    numero_parte = models.CharField("número de parte o folio", max_length=40, blank=True)
    directora_informada_en = models.DateTimeField("Directora informada el", editable=False)
    hash_constancia = models.CharField("hash de la constancia", max_length=64, unique=True, editable=False)

    class Meta:
        db_table = "denuncia"
        ordering = ["-fecha_hora_presentacion"]

    def __str__(self):
        return "Denuncia de la alerta %d" % self.alerta_id

    @property
    def dentro_de_plazo(self):
        return self.fecha_hora_presentacion <= self.alerta.plazo_denuncia

    def calcular_hash(self):
        return _hash("denuncia", self.alerta_id, self.psicologa_id, self.institucion,
                     _utc(self.fecha_hora_presentacion), self.numero_parte, _utc(self.directora_informada_en))

    def constancia_integra(self):
        return self.calcular_hash() == self.hash_constancia

    def clean(self):
        errores = {}
        if self.psicologa_id and not self.psicologa.tiene_rol("psicologa_denunciante"):
            errores["psicologa"] = "Solo la psicóloga designada puede registrar la denuncia."
        if self.alerta_id and self.fecha_hora_presentacion:
            if self.fecha_hora_presentacion < self.alerta.fecha_hora_conocimiento:
                errores["fecha_hora_presentacion"] = "La denuncia no puede ser anterior al conocimiento de la situación."
        if self.numero_parte and not self.numero_parte.replace("-", "").replace(" ", "").isalnum():
            errores["numero_parte"] = "Use solo letras, números y guiones."
        if errores:
            raise ValidationError(errores)
