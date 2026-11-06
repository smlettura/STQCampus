import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.formularios import Formulario, FormularioModelo
from apps.core.validadores import validar_adjunto
from apps.cuentas.models import Usuario, UsuarioRol
from apps.estudiantes.forms import CampoEstudiante, estudiantes_activos

from .models import Caso, Derivacion, Documento, Hito, SesionSeguimiento


def profesionales_responsables():
    ids = UsuarioRol.objects.vigentes().filter(
        rol__codigo__in=["psicologa", "asistente_social", "coordinacion_pie"]).values("usuario_id")
    return Usuario.objects.filter(pk__in=ids, activo=True)


class DerivacionForm(FormularioModelo):
    estudiante = CampoEstudiante(queryset=estudiantes_activos(), label="Estudiante")

    class Meta:
        model = Derivacion
        fields = ["estudiante", "fecha_hora", "motivo"]
        help_texts = {"motivo": "Describa lo observado y por qué deriva. Evite juicios o diagnósticos."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estudiante"].queryset = estudiantes_activos()
        self.initial.setdefault("fecha_hora", timezone.localtime().replace(second=0, microsecond=0))

    def clean_estudiante(self):
        estudiante = self.cleaned_data["estudiante"]
        if Derivacion.objects.filter(estudiante=estudiante, caso__isnull=True).exists():
            raise ValidationError("Ya existe una derivación pendiente de revisión para este estudiante.")
        return estudiante


class AbrirCasoForm(FormularioModelo):
    class Meta:
        model = Caso
        fields = ["tipo_proceso", "tipo_atencion", "responsable", "fecha_apertura"]

    def __init__(self, *args, estudiante=None, fecha_minima=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fecha_minima = fecha_minima
        if estudiante is not None:
            self.instance.estudiante = estudiante
        self.fields["responsable"].queryset = profesionales_responsables()

    def clean_fecha_apertura(self):
        fecha = self.cleaned_data["fecha_apertura"]
        if self.fecha_minima and fecha < self.fecha_minima:
            raise ValidationError("El caso no puede abrirse antes de la derivación (%s)." % self.fecha_minima.strftime("%d-%m-%Y"))
        return fecha


class CasoNuevoForm(AbrirCasoForm):
    estudiante = CampoEstudiante(queryset=estudiantes_activos(), label="Estudiante")

    class Meta(AbrirCasoForm.Meta):
        fields = ["estudiante"] + AbrirCasoForm.Meta.fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estudiante"].queryset = estudiantes_activos()


class CampoCaso(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return "%s · abierto el %s" % (obj.get_tipo_proceso_display(), obj.fecha_apertura.strftime("%d/%m/%Y"))


class AtencionForm(FormularioModelo):
    """«Registrar atención» del prototipo v1: una atención (sesión) dentro del caso del estudiante.

    Si el estudiante no tiene un caso abierto, la vista abre uno de «seguimiento psicosocial» al guardar. Si tiene más
    de uno, se pide elegir en cuál se registra.
    """

    fecha = forms.DateField(label="Fecha")
    hora = forms.TimeField(label="Hora de inicio", required=False, widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))
    caso = CampoCaso(queryset=Caso.objects.none(), label="Caso", required=False, empty_label=None)
    solo_autora = forms.BooleanField(label="Solo visible para mí", required=False,
                                     help_text="Oculta la descripción al resto del equipo psicosocial.")

    class Meta:
        model = SesionSeguimiento
        fields = ["duracion_minutos", "tipo_atencion", "urgencia", "motivo", "derivado_por", "nota", "acuerdos"]
        widgets = {
            "tipo_atencion": forms.RadioSelect, "urgencia": forms.RadioSelect,
            "nota": forms.Textarea(attrs={"rows": 5, "placeholder": "Describe lo observado, lo conversado y el estado del "
                                                                     "estudiante…", "data-minimo": "10"}),
            "acuerdos": forms.Textarea(attrs={"rows": 5, "placeholder": "Qué se acordó con el estudiante, la familia o el "
                                                                         "colegio…"}),
        }

    def __init__(self, *args, casos=None, profesional=None, estado="registrada", **kwargs):
        super().__init__(*args, **kwargs)
        self.casos = casos
        self.instance.estado = estado
        if self.instance.pk is None:
            self.instance.profesional = profesional
        ahora = timezone.localtime(self.instance.fecha_hora) if self.instance.fecha_hora else timezone.localtime()
        self.initial.setdefault("fecha", ahora.date())
        self.initial.setdefault("hora", ahora.replace(second=0, microsecond=0).time())
        self.initial.setdefault("solo_autora", self.instance.nivel_acceso == "autora")
        self.fields["derivado_por"].choices = [("", "Sin derivación")] + list(SesionSeguimiento.DERIVANTES)
        self.fields["motivo"].choices = [("", "Seleccionar motivo")] + list(SesionSeguimiento.MOTIVOS)
        if self.instance.pk is None and not self.is_bound:
            self.initial["motivo"] = ""
        self.fields["nota"].required = False
        self.fields["duracion_minutos"].widget.choices = SesionSeguimiento.DURACIONES
        if self.instance.pk or casos is None or casos.count() < 2:
            del self.fields["caso"]
            if self.instance.pk is None and casos is not None and casos.count() == 1:
                self.instance.caso = casos.first()
        else:
            self.fields["caso"].queryset = casos
            self.fields["caso"].required = True

    def clean(self):
        datos = super().clean()
        fecha, hora = datos.get("fecha"), datos.get("hora")
        if fecha:
            momento = timezone.make_aware(datetime.datetime.combine(fecha, hora or datetime.time(0, 0)))
            if momento > timezone.now() + datetime.timedelta(minutes=5):
                self.add_error("fecha" if not hora else "hora", "La atención no puede quedar en el futuro.")
            self.instance.fecha_hora = momento
        if datos.get("caso"):
            self.instance.caso = datos["caso"]
        self.instance.nivel_acceso = "autora" if datos.get("solo_autora") else "equipo"
        return datos

    def add_error(self, field, error):
        # La validación del modelo informa los errores de fecha en «fecha_hora», que aquí se muestran en «Fecha».
        if field == "fecha_hora":
            field = "fecha"
        elif isinstance(error, ValidationError) and hasattr(error, "error_dict") and "fecha_hora" in error.error_dict:
            error.error_dict["fecha"] = error.error_dict.pop("fecha_hora")
        super().add_error(field, error)


class HitoForm(FormularioModelo):
    class Meta:
        model = Hito
        fields = ["tipo", "descripcion", "fecha", "visible_profesor_jefe"]
        help_texts = {"visible_profesor_jefe": "Marque solo información útil para el aula; nunca contenido clínico."}

    def __init__(self, *args, caso=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.caso = caso

    def clean(self):
        datos = super().clean()
        if datos.get("visible_profesor_jefe") and datos.get("tipo") == "hallazgo":
            self.add_error("visible_profesor_jefe", "Los hallazgos son información del equipo y no se comparten con el "
                                                    "profesor jefe.")
        return datos


class DocumentoForm(Formulario):
    tipo = forms.ChoiceField(label="Tipo de documento", choices=Documento.TIPOS)
    archivo = forms.FileField(label="Archivo (PDF, JPG o PNG)", validators=[validar_adjunto],
                              widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png"}))


class CerrarCasoForm(Formulario):
    fecha_cierre = forms.DateField(label="Fecha de cierre")
    confirmar = forms.BooleanField(label="Confirmo que el acompañamiento terminó y que el caso queda solo como registro.")

    def __init__(self, *args, caso=None, **kwargs):
        self.caso = caso
        super().__init__(*args, **kwargs)
        self.initial.setdefault("fecha_cierre", timezone.localdate())

    def clean_fecha_cierre(self):
        fecha = self.cleaned_data["fecha_cierre"]
        if fecha > timezone.localdate():
            raise ValidationError("La fecha de cierre no puede estar en el futuro.")
        if fecha < self.caso.fecha_apertura:
            raise ValidationError("La fecha de cierre no puede ser anterior a la apertura.")
        ultima = self.caso.sesiones.order_by("-fecha_hora").first()
        if ultima and fecha < timezone.localtime(ultima.fecha_hora).date():
            raise ValidationError("Hay sesiones registradas después de esa fecha.")
        return fecha

    def clean(self):
        datos = super().clean()
        abiertas = self.caso.evaluaciones.filter(estado="en_proceso").count()
        if abiertas:
            raise ValidationError("Hay %d evaluación(es) diagnóstica(s) en proceso. Ciérrelas antes de cerrar el caso." % abiertas)
        if self.caso.informes.filter(estado="borrador").exists():
            raise ValidationError("Hay informes en borrador. Valídelos o elimínelos antes de cerrar el caso.")
        return datos
