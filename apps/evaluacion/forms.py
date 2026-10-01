from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.formularios import Formulario, FormularioModelo
from apps.cuentas.models import Usuario, UsuarioRol
from apps.cumplimiento.models import Consentimiento

from .models import EvaluacionDiagnostica, Informe, ParticipacionEvaluacion, PlanApoyo


class EvaluacionForm(FormularioModelo):
    class Meta:
        model = EvaluacionDiagnostica
        fields = ["tipo_evaluacion", "tipo_nee", "fecha_evaluacion", "fecha_reevaluacion", "diagnostico"]
        help_texts = {"diagnostico": "Se guarda cifrado. Puede completarlo al cierre de la evaluación.",
                      "tipo_nee": "Por ejemplo: trastorno específico del lenguaje, TEA, discapacidad intelectual leve."}

    def __init__(self, *args, caso=None, **kwargs):
        super().__init__(*args, **kwargs)
        if caso is not None:
            self.instance.caso = caso

    def clean(self):
        datos = super().clean()
        caso = self.instance.caso
        # RF-11 y Decreto 170: la evaluación requiere la autorización del apoderado.
        if not self.instance.pk and not Consentimiento.vigente_para(caso.estudiante, "evaluacion_pie"):
            raise ValidationError("No hay un consentimiento vigente del apoderado para la evaluación diagnóstica "
                                  "integral. Regístrelo en Cumplimiento antes de continuar.")
        return datos


def profesionales_evaluacion():
    ids = UsuarioRol.objects.vigentes().filter(
        rol__codigo__in=["psicologa", "asistente_social", "coordinacion_pie"]).values("usuario_id")
    return Usuario.objects.filter(pk__in=ids, activo=True)


class ParticipacionForm(FormularioModelo):
    class Meta:
        model = ParticipacionEvaluacion
        fields = ["usuario", "rol_profesional", "aporte", "fecha"]

    def __init__(self, *args, evaluacion=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.evaluacion = evaluacion
        self.fields["usuario"].queryset = profesionales_evaluacion()
        self.fields["usuario"].label = "Profesional"


class PlanForm(FormularioModelo):
    class Meta:
        model = PlanApoyo
        fields = ["tipo", "evaluacion", "fecha_inicio", "fecha_termino", "adecuaciones", "detalle"]

    def __init__(self, *args, estudiante=None, **kwargs):
        super().__init__(*args, **kwargs)
        if estudiante is not None:
            self.instance.estudiante = estudiante
        estudiante = self.instance.estudiante
        self.fields["evaluacion"].queryset = EvaluacionDiagnostica.objects.filter(caso__estudiante=estudiante)
        self.initial.setdefault("fecha_inicio", timezone.localdate())

    def clean_adecuaciones(self):
        texto = self.cleaned_data["adecuaciones"].strip()
        if len(texto) < 15:
            raise ValidationError("Describa las adecuaciones con al menos 15 caracteres.")
        return texto


class CerrarPlanForm(Formulario):
    fecha_termino = forms.DateField(label="Fecha de término")

    def __init__(self, *args, plan=None, **kwargs):
        self.plan = plan
        super().__init__(*args, **kwargs)
        self.initial.setdefault("fecha_termino", timezone.localdate())

    def clean_fecha_termino(self):
        fecha = self.cleaned_data["fecha_termino"]
        if fecha < self.plan.fecha_inicio:
            raise ValidationError("No puede ser anterior al inicio del plan.")
        if fecha > timezone.localdate():
            raise ValidationError("No puede estar en el futuro.")
        return fecha


class InformeForm(FormularioModelo):
    class Meta:
        model = Informe
        fields = ["tipo", "contenido"]
        help_texts = {"contenido": "Se guarda cifrado. Los formularios oficiales se completan en su formato vigente."}

    def __init__(self, *args, caso=None, **kwargs):
        super().__init__(*args, **kwargs)
        if caso is not None:
            self.instance.caso = caso
        self.fields["contenido"].widget.attrs["rows"] = 16

    def clean_contenido(self):
        texto = self.cleaned_data["contenido"].strip()
        if len(texto) < 50:
            raise ValidationError("El informe debe tener al menos 50 caracteres.")
        if "[VERIFICAR" in texto.upper():
            raise ValidationError("El texto aún tiene marcas [VERIFICAR] del copiloto. Revíselas antes de guardar.")
        return texto


class EntregaInformeForm(Formulario):
    fecha_entrega = forms.DateField(label="Fecha de la reunión de entrega")
    confirmar = forms.BooleanField(label="Confirmo que el informe se entregó en una reunión presencial con el apoderado.")

    def __init__(self, *args, informe=None, **kwargs):
        self.informe = informe
        super().__init__(*args, **kwargs)
        self.initial.setdefault("fecha_entrega", timezone.localdate())

    def clean_fecha_entrega(self):
        fecha = self.cleaned_data["fecha_entrega"]
        if fecha > timezone.localdate():
            raise ValidationError("No puede estar en el futuro.")
        if fecha < self.informe.caso.fecha_apertura:
            raise ValidationError("No puede ser anterior a la apertura del caso.")
        return fecha

