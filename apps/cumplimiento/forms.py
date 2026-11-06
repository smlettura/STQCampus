from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.casos.models import Documento
from apps.core.formularios import Formulario, FormularioModelo
from apps.estudiantes.models import Apoderado

from .models import Consentimiento, RetencionEliminacion, SolicitudARCO


class ConsentimientoForm(FormularioModelo):
    class Meta:
        model = Consentimiento
        fields = ["apoderado", "alcance", "fecha_otorgamiento", "documento"]

    def __init__(self, *args, estudiante=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.estudiante = estudiante
        self.fields["apoderado"].queryset = Apoderado.objects.filter(vinculos_estudiante__estudiante=estudiante)
        self.fields["documento"].queryset = Documento.objects.filter(caso__estudiante=estudiante)
        self.fields["documento"].required = False
        self.initial.setdefault("fecha_otorgamiento", timezone.localdate())


class RevocarConsentimientoForm(Formulario):
    fecha_revocacion = forms.DateField(label="Fecha de revocación")

    def __init__(self, *args, consentimiento=None, **kwargs):
        self.consentimiento = consentimiento
        super().__init__(*args, **kwargs)
        self.initial.setdefault("fecha_revocacion", timezone.localdate())

    def clean_fecha_revocacion(self):
        fecha = self.cleaned_data["fecha_revocacion"]
        if fecha < self.consentimiento.fecha_otorgamiento:
            raise ValidationError("No puede ser anterior al otorgamiento.")
        if fecha > timezone.localdate():
            raise ValidationError("No puede estar en el futuro.")
        return fecha


class SolicitudARCOForm(FormularioModelo):
    class Meta:
        model = SolicitudARCO
        fields = ["apoderado", "tipo_derecho", "fecha_recepcion"]

    def __init__(self, *args, estudiante=None, responsable=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.estudiante = estudiante
        self.instance.responsable = responsable
        self.fields["apoderado"].queryset = Apoderado.objects.filter(vinculos_estudiante__estudiante=estudiante)


class RespuestaARCOForm(FormularioModelo):
    class Meta:
        model = SolicitudARCO
        fields = ["estado", "fecha_respuesta"]


class DecisionRetencionForm(Formulario):
    accion = forms.ChoiceField(label="Acción", choices=RetencionEliminacion.ACCIONES,
                               help_text="Anonimizar conserva datos agregados sin identificar; eliminar borra el expediente.")
    decision = forms.ChoiceField(label="Decisión", choices=[("autorizar", "Autorizar"), ("postergar", "Postergar")],
                                 widget=forms.RadioSelect)
    confirmar = forms.BooleanField(label="Confirmo que revisé el expediente y que no existen obligaciones legales o "
                                         "procesos pendientes que exijan conservarlo.", required=False)

    def clean(self):
        datos = super().clean()
        if datos.get("decision") == "autorizar" and not datos.get("confirmar"):
            self.add_error("confirmar", "Debe confirmar la revisión para autorizar.")
        return datos
