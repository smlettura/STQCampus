from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.casos.models import Documento
from apps.core.formularios import Formulario, FormularioModelo
from apps.core.validadores import normalizar_rut, normalizar_telefono
from apps.estudiantes.models import Apoderado, Estudiante

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
        fields = ["apoderado", "tipo_derecho", "fecha_recepcion", "detalle"]
        widgets = {"detalle": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, estudiante=None, responsable=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.estudiante = estudiante
        self.instance.responsable = responsable
        self.fields["apoderado"].queryset = Apoderado.objects.filter(vinculos_estudiante__estudiante=estudiante)


class RespuestaARCOForm(FormularioModelo):
    class Meta:
        model = SolicitudARCO
        fields = ["estado", "fecha_respuesta", "respuesta"]
        widgets = {"respuesta": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial.setdefault("fecha_respuesta", timezone.localdate())


class RectificacionEstudianteForm(FormularioModelo):
    """Datos del estudiante que el titular puede pedir corregir."""

    class Meta:
        model = Estudiante
        fields = ["rut", "primer_nombre", "segundo_nombre", "apellido_paterno", "apellido_materno", "nombre_social",
                  "fecha_nacimiento"]

    def clean_rut(self):
        rut = normalizar_rut(self.cleaned_data["rut"])
        if Estudiante.objects.filter(rut=rut).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Ya existe un estudiante con este RUT.")
        return rut


class RectificacionApoderadoForm(FormularioModelo):
    """Datos de contacto del apoderado que ejerce el derecho."""
    prefix = "apo"

    class Meta:
        model = Apoderado
        fields = ["nombre_completo", "telefono", "correo"]

    def clean_telefono(self):
        return normalizar_telefono(self.cleaned_data.get("telefono"))


class SupresionForm(Formulario):
    accion = forms.ChoiceField(label="Qué se propone a la Dirección", choices=RetencionEliminacion.ACCIONES,
                               initial="anonimizar",
                               help_text="Anonimizar conserva datos agregados sin identificar; eliminar borra el expediente.")
    confirmar = forms.BooleanField(label="Revisé que no existe una obligación legal de conservar el expediente "
                                         "(por ejemplo, un proceso judicial o de la Superintendencia en curso).")


class OposicionForm(Formulario):
    alcances = forms.MultipleChoiceField(label="Tratamientos a los que se opone", widget=forms.CheckboxSelectMultiple,
                                         help_text="Se revocan hoy los consentimientos vigentes marcados.")

    def __init__(self, *args, estudiante=None, **kwargs):
        super().__init__(*args, **kwargs)
        vigentes = estudiante.consentimientos.filter(fecha_revocacion__isnull=True).values_list("alcance", flat=True)
        nombres = dict(Consentimiento.ALCANCES)
        self.fields["alcances"].choices = [(a, nombres.get(a, a)) for a in sorted(set(vigentes))]


class BloqueoForm(Formulario):
    motivo = forms.CharField(label="Motivo del bloqueo", max_length=255,
                             help_text="Sin datos personales. Ej.: «Mientras se resuelve la rectificación solicitada».")


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
