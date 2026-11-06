import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.formularios import Formulario, FormularioModelo
from apps.core.validadores import FIRMAS_EXCEL, normalizar_rut, normalizar_telefono, validar_adjunto
from apps.cuentas.models import Usuario, UsuarioRol

from .models import Apoderado, Curso, Estudiante, EstudianteApoderado


class CampoEstudiante(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return "%s, %s — %s" % (obj.apellidos, obj.nombres, obj.curso.nombre)


class CampoCurso(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return "%s · %s" % (obj.nombre, obj.anio_escolar)


def estudiantes_activos():
    return (Estudiante.objects.activos().select_related("curso", "curso__sede")
            .order_by("apellido_paterno", "apellido_materno", "primer_nombre"))


def cursos_vigentes():
    anio = timezone.localdate().year
    return Curso.objects.filter(anio_escolar__gte=anio - 1, anio_escolar__lte=anio + 1).ordenados().select_related("sede")


class EstudianteForm(FormularioModelo):
    """Registrar / editar estudiante (pantalla «Registrar estudiante» del prototipo v1)."""

    curso = CampoCurso(queryset=Curso.objects.none(), label="Curso", empty_label="Seleccionar curso")

    class Meta:
        model = Estudiante
        fields = ["rut", "fecha_nacimiento", "nombre_social", "primer_nombre", "segundo_nombre", "apellido_paterno",
                  "apellido_materno", "curso", "fecha_ingreso", "necesidad_educativa", "en_pie", "prioritario",
                  "matricula_condicional"]
        widgets = {"rut": forms.TextInput(attrs={"placeholder": "12.345.678-9", "autocomplete": "off"}),
                   "nombre_social": forms.TextInput(attrs={"placeholder": "Opcional"})}
        help_texts = {"en_pie": "", "prioritario": "", "nombre_social": ""}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["curso"].queryset = cursos_vigentes()
        for campo in ("primer_nombre", "segundo_nombre", "apellido_paterno", "apellido_materno", "nombre_social"):
            self.fields[campo].widget.attrs.setdefault("autocomplete", "off")
        self.fields["necesidad_educativa"].help_text = "Obligatoria para estudiantes del PIE."

    def clean_rut(self):
        rut = normalizar_rut(self.cleaned_data["rut"])
        if Estudiante.objects.filter(rut=rut).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Ya existe un estudiante con este RUT.")
        return rut


class ApoderadoRapidoForm(Formulario):
    """Sección opcional «Apoderado» del registro: contacto principal para comunicaciones."""

    prefix = "apo"
    nombre_completo = forms.CharField(label="Nombre completo", max_length=120, required=False)
    telefono = forms.CharField(label="Teléfono", max_length=20, required=False,
                               widget=forms.TextInput(attrs={"placeholder": "+56 9 …", "autocomplete": "off"}))
    correo = forms.EmailField(label="Correo", max_length=120, required=False,
                              widget=forms.EmailInput(attrs={"placeholder": "correo@ejemplo.cl", "autocomplete": "off"}))
    parentesco = forms.ChoiceField(label="Parentesco", choices=EstudianteApoderado.PARENTESCOS, initial="madre")

    def tiene_datos(self):
        return any((self.cleaned_data.get(k) or "").strip() for k in ("nombre_completo", "telefono", "correo"))

    def clean_telefono(self):
        return normalizar_telefono(self.cleaned_data.get("telefono"))

    def clean(self):
        datos = super().clean()
        if not self.tiene_datos():
            return datos
        apoderado = Apoderado(nombre_completo=datos.get("nombre_completo", ""), telefono=datos.get("telefono", ""),
                              correo=datos.get("correo", ""))
        try:
            apoderado.full_clean(exclude=["rut"])
        except ValidationError as e:
            for campo, errores in e.message_dict.items():
                self.add_error(campo if campo in self.fields else None, errores)
        self.apoderado = apoderado
        return datos

    def guardar(self, estudiante):
        if not self.tiene_datos():
            return None
        self.apoderado.save()
        return EstudianteApoderado.objects.create(estudiante=estudiante, apoderado=self.apoderado,
                                                  parentesco=self.cleaned_data["parentesco"], es_titular=True)


class VincularApoderadoForm(Formulario):
    """Busca al apoderado por RUT; si no existe, lo crea con los datos ingresados."""

    rut = forms.CharField(label="RUT del apoderado", max_length=12)
    nombre_completo = forms.CharField(label="Nombre completo", max_length=120, required=False,
                                      help_text="Solo si el apoderado no está registrado.")
    telefono = forms.CharField(label="Teléfono", max_length=20, required=False)
    correo = forms.EmailField(label="Correo", max_length=120, required=False)
    parentesco = forms.ChoiceField(label="Parentesco", choices=EstudianteApoderado.PARENTESCOS)
    es_titular = forms.BooleanField(label="Apoderado titular", required=False)

    def __init__(self, *args, estudiante=None, **kwargs):
        self.estudiante = estudiante
        self.apoderado = None
        super().__init__(*args, **kwargs)

    def clean_rut(self):
        return normalizar_rut(self.cleaned_data["rut"])

    def clean_telefono(self):
        return normalizar_telefono(self.cleaned_data.get("telefono"))

    def clean(self):
        datos = super().clean()
        rut = datos.get("rut")
        if not rut:
            return datos
        self.apoderado = Apoderado.objects.filter(rut=rut).first()
        if self.apoderado is None:
            nuevo = Apoderado(rut=rut, nombre_completo=datos.get("nombre_completo", ""),
                              telefono=datos.get("telefono", ""), correo=datos.get("correo", ""))
            try:
                nuevo.full_clean()
            except ValidationError as e:
                for campo, errores in e.message_dict.items():
                    self.add_error(campo if campo in self.fields else None, errores)
                return datos
            self.apoderado = nuevo
        vinculo = EstudianteApoderado(estudiante=self.estudiante, apoderado=self.apoderado,
                                      parentesco=datos.get("parentesco"), es_titular=datos.get("es_titular", False))
        if self.apoderado.pk:
            try:
                vinculo.full_clean(exclude=["apoderado", "estudiante"])
            except ValidationError as e:
                self.add_error(None, e)
        elif vinculo.es_titular and self.estudiante.vinculos_apoderado.filter(es_titular=True).exists():
            self.add_error("es_titular", "El estudiante ya tiene un apoderado titular.")
        self.vinculo = vinculo
        return datos

    def save(self):
        if not self.apoderado.pk:
            self.apoderado.save()
        self.vinculo.apoderado = self.apoderado
        self.vinculo.save()
        return self.vinculo


class ApoderadoForm(FormularioModelo):
    class Meta:
        model = Apoderado
        fields = ["rut", "nombre_completo", "telefono", "correo"]


class MarcarInactivoForm(Formulario):
    fecha_retiro = forms.DateField(label="Fecha de retiro")
    confirmar = forms.BooleanField(label="Confirmo que el estudiante se retiró del colegio. Su ficha y sus registros se "
                                         "conservan según la política de retención.")

    def __init__(self, *args, estudiante=None, **kwargs):
        self.estudiante = estudiante
        super().__init__(*args, **kwargs)
        self.initial.setdefault("fecha_retiro", timezone.localdate())

    def clean_fecha_retiro(self):
        fecha = self.cleaned_data["fecha_retiro"]
        if fecha > timezone.localdate():
            raise ValidationError("La fecha de retiro no puede estar en el futuro.")
        minimo = self.estudiante.fecha_ingreso or self.estudiante.fecha_nacimiento
        if fecha <= minimo:
            raise ValidationError("La fecha de retiro debe ser posterior al %s." % minimo.strftime("%d-%m-%Y"))
        if self.estudiante.casos.exclude(estado="cerrado").exists():
            raise ValidationError("El estudiante tiene casos abiertos en el equipo psicosocial: ciérrelos o "
                                  "coordine con el equipo antes de registrar el retiro.")
        return fecha


class ImportarForm(Formulario):
    archivo = forms.FileField(label="Planilla Excel (.xlsx)",
                              validators=[lambda a: validar_adjunto(a, FIRMAS_EXCEL)],
                              widget=forms.ClearableFileInput(attrs={"accept": ".xlsx"}))


class CursoForm(FormularioModelo):
    class Meta:
        model = Curso
        fields = ["sede", "nivel", "letra", "anio_escolar", "profesor_jefe"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        profesores = UsuarioRol.objects.vigentes().filter(rol__codigo="profesor_jefe").values("usuario_id")
        self.fields["profesor_jefe"].queryset = Usuario.objects.filter(pk__in=profesores, activo=True)
        if not self.instance.pk:
            self.initial.setdefault("anio_escolar", timezone.localdate().year)

    def clean(self):
        datos = super().clean()
        sede, nivel, letra, anio = (datos.get(k) for k in ("sede", "nivel", "letra", "anio_escolar"))
        if sede and nivel and letra and anio and Curso.objects.filter(
                sede=sede, nivel=nivel, letra=letra.upper(), anio_escolar=anio).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Ese curso ya existe para el año y la sede indicados.")
        return datos


# ---------------------------------------------------------------------------------------------- importación masiva
COLUMNAS_IMPORTACION = [
    ("rut", "RUT *"), ("primer_nombre", "Primer nombre *"), ("segundo_nombre", "Segundo nombre"),
    ("apellido_paterno", "Apellido paterno *"), ("apellido_materno", "Apellido materno *"),
    ("nombre_social", "Nombre social"), ("fecha_nacimiento", "Fecha de nacimiento *"), ("curso", "Curso *"),
    ("fecha_ingreso", "Fecha de ingreso"), ("pie", "PIE"), ("nee", "NEE"), ("prioritario", "Prioritario"),
    ("apoderado", "Apoderado"), ("telefono_apoderado", "Teléfono apoderado"), ("correo_apoderado", "Correo apoderado"),
]
ROTULOS_ERROR = {**{c: r.replace(" *", "") for c, r in COLUMNAS_IMPORTACION}, "en_pie": "PIE", "necesidad_educativa": "NEE",
                 "nombre_completo": "Apoderado", "telefono": "Teléfono apoderado", "correo": "Correo apoderado"}
_SI = {"si", "sí", "s", "x", "1", "true", "verdadero"}
_NEE = {"": "ninguna", "ninguna": "ninguna", "no": "ninguna", "transitoria": "transitoria", "permanente": "permanente"}


def _fecha_excel(valor):
    if valor in (None, ""):
        return None
    if isinstance(valor, datetime.datetime):
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor
    for formato in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(str(valor).strip(), formato).date()
        except ValueError:
            continue
    raise ValidationError("Fecha no válida: use dd-mm-aaaa.")


def _texto(valor):
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return " ".join(str(valor).split())


def validar_importacion(filas, anio):
    """Valida todas las filas antes de guardar. Devuelve (estudiantes listos, errores [(fila, mensaje)])."""
    from apps.core.documentos import normalizar_encabezado

    cursos = {normalizar_encabezado(c.nombre): c for c in Curso.objects.filter(anio_escolar=anio)}
    listos, errores, ruts = [], [], set()
    for numero, datos in filas:
        d = {clave: datos.get(normalizar_encabezado(rotulo)) for clave, rotulo in COLUMNAS_IMPORTACION}
        try:
            curso = cursos.get(normalizar_encabezado(_texto(d["curso"])))
            if curso is None:
                raise ValidationError("Curso «%s» no existe en %s (use por ejemplo «5° Básico A»)." % (_texto(d["curso"]), anio))
            nee = _NEE.get(_texto(d["nee"]).lower())
            if nee is None:
                raise ValidationError("NEE debe ser «transitoria», «permanente» o quedar vacía.")
            e = Estudiante(rut=_texto(d["rut"]), primer_nombre=_texto(d["primer_nombre"]),
                           segundo_nombre=_texto(d["segundo_nombre"]), apellido_paterno=_texto(d["apellido_paterno"]),
                           apellido_materno=_texto(d["apellido_materno"]), nombre_social=_texto(d["nombre_social"]),
                           fecha_nacimiento=_fecha_excel(d["fecha_nacimiento"]), curso=curso,
                           fecha_ingreso=_fecha_excel(d["fecha_ingreso"]), necesidad_educativa=nee,
                           en_pie=_texto(d["pie"]).lower() in _SI, prioritario=_texto(d["prioritario"]).lower() in _SI)
            e.full_clean(validate_unique=False)
            if e.rut in ruts:
                raise ValidationError("El RUT %s está repetido en la planilla." % e.rut_formateado)
            if Estudiante.objects.filter(rut=e.rut).exists():
                raise ValidationError("Ya existe un estudiante con el RUT %s." % e.rut_formateado)
            ruts.add(e.rut)
            apoderado = None
            if any(_texto(d[k]) for k in ("apoderado", "telefono_apoderado", "correo_apoderado")):
                apoderado = Apoderado(nombre_completo=_texto(d["apoderado"]), telefono=_texto(d["telefono_apoderado"]),
                                      correo=_texto(d["correo_apoderado"]))
                apoderado.full_clean(exclude=["rut"])
            listos.append((e, apoderado))
        except ValidationError as ex:
            mensajes = []
            if hasattr(ex, "message_dict"):
                for campo, msgs in ex.message_dict.items():
                    rotulo = ROTULOS_ERROR.get(campo, campo)
                    mensajes += ["%s: %s" % (rotulo, m) if campo != "__all__" else m for m in msgs]
            else:
                mensajes = ex.messages
            errores.append((numero, "; ".join(mensajes)))
    return listos, errores
