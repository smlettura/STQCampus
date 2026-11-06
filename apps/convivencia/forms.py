from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.formularios import Formulario, FormularioModelo
from apps.core.validadores import FIRMAS_EVIDENCIA, validar_adjunto
from apps.cuentas.models import Usuario, UsuarioRol
from apps.estudiantes.forms import CampoEstudiante, estudiantes_activos
from apps.estudiantes.models import Curso, Estudiante

from .models import ActividadPlan, Anotacion, Conflicto, ProtocoloActivado, RegistroConductual

ROLES_CONVIVENCIA = ["encargada_convivencia", "psicologa", "asistente_social", "inspectoria", "directora",
                     "coordinacion_pie"]


def usuarios_con_roles(roles):
    ids = UsuarioRol.objects.vigentes().filter(rol__codigo__in=roles).values("usuario_id")
    return Usuario.objects.filter(pk__in=ids, activo=True)


class CampoCursoCorto(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.nombre


def cursos_del_anio():
    return Curso.objects.filter(anio_escolar=timezone.localdate().year).ordenados()


class CampoParticipantes(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return "%s — %s" % (obj.nombre_lista, obj.curso.nombre)


class ConflictoForm(FormularioModelo):
    curso = CampoCursoCorto(queryset=Curso.objects.none(), label="Curso", empty_label="Seleccionar curso")
    participantes = CampoParticipantes(queryset=Estudiante.objects.none(), label="Estudiantes participantes",
                                       widget=forms.SelectMultiple(attrs={"size": 8}),
                                       help_text="Mantenga presionada la tecla Ctrl (o Cmd) para elegir varios.")

    class Meta:
        model = Conflicto
        fields = ["fecha", "tipo_gestion", "curso", "participantes", "encargada", "descripcion", "acuerdos", "resultado"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 4}), "acuerdos": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["curso"].queryset = cursos_del_anio() if not self.instance.pk else Curso.objects.filter(
            anio_escolar=self.instance.curso.anio_escolar).ordenados()
        self.fields["participantes"].queryset = estudiantes_activos() if not self.instance.pk else Estudiante.objects.filter(
            curso__anio_escolar=self.instance.curso.anio_escolar).select_related("curso")
        self.fields["encargada"].queryset = usuarios_con_roles(ROLES_CONVIVENCIA)
        if usuario is not None and not self.instance.pk:
            self.initial.setdefault("encargada", usuario.pk)


class AnotacionForm(FormularioModelo):
    estudiante = CampoEstudiante(queryset=Estudiante.objects.none(), label="Estudiante")

    class Meta:
        model = Anotacion
        fields = ["estudiante", "fecha", "tipo", "descripcion"]
        widgets = {"tipo": forms.RadioSelect, "descripcion": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, estudiantes=None, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estudiante"].queryset = estudiantes if estudiantes is not None else estudiantes_activos()
        self.instance.registrada_por = usuario


class RegistroConductualForm(FormularioModelo):
    estudiante = CampoEstudiante(queryset=Estudiante.objects.none(), label="Estudiante")

    class Meta:
        model = RegistroConductual
        fields = ["estudiante", "fecha", "categoria", "porcentaje_asistencia", "descripcion"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 4}),
                   "porcentaje_asistencia": forms.NumberInput(attrs={"step": "0.1", "min": "0", "max": "100"})}

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estudiante"].queryset = estudiantes_activos()
        self.instance.registrado_por = usuario


class ProtocoloForm(FormularioModelo):
    curso = CampoCursoCorto(queryset=Curso.objects.none(), label="Curso", empty_label="Seleccionar curso", required=False,
                            help_text="Si indica un estudiante, se usa su curso.")
    estudiante = CampoEstudiante(queryset=Estudiante.objects.none(), label="Estudiante (opcional)", required=False)

    class Meta:
        model = ProtocoloActivado
        fields = ["protocolo", "fecha_activacion", "curso", "estudiante", "responsable", "observaciones"]
        widgets = {"observaciones": forms.Textarea(attrs={"rows": 4})}
        help_texts = {"observaciones": "Antecedentes y primeras acciones. Se guarda cifrado."}

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["curso"].queryset = cursos_del_anio()
        self.fields["estudiante"].queryset = estudiantes_activos()
        self.fields["responsable"].queryset = usuarios_con_roles(ROLES_CONVIVENCIA)
        if usuario is not None:
            self.initial.setdefault("responsable", usuario.pk)

    def clean(self):
        datos = super().clean()
        e, curso = datos.get("estudiante"), datos.get("curso")
        if e and not curso:
            datos["curso"] = e.curso
        elif not e and not curso:
            self.add_error("curso", "Indique el curso (o el estudiante).")
        return datos


class CerrarProtocoloForm(Formulario):
    fecha_cierre = forms.DateField(label="Fecha de cierre")
    observaciones = forms.CharField(label="Acciones realizadas y cierre", widget=forms.Textarea(attrs={"rows": 5}),
                                    min_length=20)

    def __init__(self, *args, protocolo=None, **kwargs):
        self.protocolo = protocolo
        super().__init__(*args, **kwargs)
        self.initial.setdefault("fecha_cierre", timezone.localdate())
        self.initial.setdefault("observaciones", protocolo.observaciones if protocolo else "")

    def clean_fecha_cierre(self):
        fecha = self.cleaned_data["fecha_cierre"]
        if fecha > timezone.localdate():
            raise ValidationError("La fecha de cierre no puede estar en el futuro.")
        if fecha < self.protocolo.fecha_activacion:
            raise ValidationError("La fecha de cierre no puede ser anterior a la activación.")
        return fecha


class ActividadForm(FormularioModelo):
    class Meta:
        model = ActividadPlan
        fields = ["tipo", "titulo", "fecha", "responsable", "medio_verificacion", "descripcion", "estado"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 4}), "estado": forms.RadioSelect}

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["responsable"].queryset = usuarios_con_roles(ROLES_CONVIVENCIA)
        if usuario is not None and not self.instance.pk:
            self.initial.setdefault("responsable", usuario.pk)


class EvidenciaForm(Formulario):
    archivo = forms.FileField(label="Archivo (PDF, imagen, Word, PowerPoint o Excel)",
                              validators=[lambda a: validar_adjunto(a, FIRMAS_EVIDENCIA)],
                              widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png,.docx,.pptx,.xlsx"}))
