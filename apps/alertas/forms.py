from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.casos.models import Caso
from apps.core.formularios import Formulario, FormularioModelo
from apps.estudiantes.forms import CampoEstudiante, estudiantes_activos

from .models import AlertaRiesgo, Denuncia, GestionAlerta


class AlertaForm(FormularioModelo):
    estudiante = CampoEstudiante(queryset=estudiantes_activos(), label="Estudiante")

    class Meta:
        model = AlertaRiesgo
        fields = ["estudiante", "sede", "tipo_situacion", "subtipo_violencia", "fecha_hora_conocimiento", "descripcion",
                  "posible_delito"]
        help_texts = {
            "sede": "Sede donde ocurrió o se detectó la situación. Si la deja vacía se usa la sede del curso.",
            "descripcion": "Relate solo hechos observados o relatados, con fecha y lugar. Se guarda cifrado.",
            "subtipo_violencia": "Solo para violencia o maltrato.",
            "posible_delito": "Márquelo si los hechos podrían constituir delito (obligación de denunciar en 24 horas).",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estudiante"].queryset = estudiantes_activos()
        self.fields["sede"].required = False
        self.initial.setdefault("fecha_hora_conocimiento", timezone.localtime().replace(second=0, microsecond=0))

    def clean(self):
        datos = super().clean()
        if not datos.get("sede") and datos.get("estudiante"):
            datos["sede"] = datos["estudiante"].curso.sede
        return datos


class GestionForm(FormularioModelo):
    class Meta:
        model = GestionAlerta
        fields = ["accion", "detalle", "fecha_hora"]

    def __init__(self, *args, alerta=None, responsable=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.alerta = alerta
        self.instance.responsable = responsable
        self.initial.setdefault("fecha_hora", timezone.localtime().replace(second=0, microsecond=0))


class DenunciaForm(FormularioModelo):
    fuera_de_plazo = forms.BooleanField(
        label="Confirmo que la denuncia se presentó después de las 24 horas desde el conocimiento de los hechos.",
        required=False)

    class Meta:
        model = Denuncia
        fields = ["institucion", "fecha_hora_presentacion", "numero_parte"]

    def __init__(self, *args, alerta=None, psicologa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.alerta = alerta
        self.instance.alerta = alerta
        self.instance.psicologa = psicologa
        self.initial.setdefault("fecha_hora_presentacion", timezone.localtime().replace(second=0, microsecond=0))

    def clean(self):
        datos = super().clean()
        presentacion = datos.get("fecha_hora_presentacion")
        if presentacion and presentacion > self.alerta.plazo_denuncia and not datos.get("fuera_de_plazo"):
            self.add_error("fuera_de_plazo", "La fecha supera el plazo legal de 24 horas (vencía el %s). Confírmelo "
                                             "expresamente." % timezone.localtime(self.alerta.plazo_denuncia).strftime("%d-%m-%Y %H:%M"))
        return datos


class VincularCasoForm(Formulario):
    caso = forms.ModelChoiceField(queryset=Caso.objects.none(), label="Caso del estudiante")

    def __init__(self, *args, alerta=None, casos=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["caso"].queryset = casos.filter(estudiante=alerta.estudiante)

    def clean_caso(self):
        caso = self.cleaned_data["caso"]
        if caso.cerrado:
            raise ValidationError("El caso está cerrado.")
        return caso
