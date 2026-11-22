"""Utilidades de formularios: widgets de fecha nativos del navegador y estilos comunes."""
from django import forms


class FechaInput(forms.DateInput):
    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%d")


class FechaHoraInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%dT%H:%M")


class FormularioBase:
    """Mezcla para formularios: aplica widgets de fecha, clases CSS y atributos de accesibilidad."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, campo in self.fields.items():
            if isinstance(campo, forms.DateTimeField):
                campo.widget = FechaHoraInput()
                campo.input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"]
            elif isinstance(campo, forms.DateField):
                campo.widget = FechaInput()
                campo.input_formats = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"]
            widget = campo.widget
            if isinstance(widget, (forms.CheckboxInput,)):
                widget.attrs.setdefault("class", "casilla")
            elif isinstance(widget, (forms.CheckboxSelectMultiple, forms.RadioSelect)):
                pass
            else:
                widget.attrs.setdefault("class", "campo")
            if campo.required:
                widget.attrs.setdefault("aria-required", "true")
            _ocultar_etiquetas(campo)


def _ocultar_etiquetas(campo):
    """Modo privado: las listas desplegables de estudiantes y apoderados muestran solo iniciales."""
    from apps.core import privacidad
    if not isinstance(campo, forms.ModelChoiceField) or not privacidad.activo():
        return
    modelo = campo.queryset.model._meta.label_lower
    if modelo in ("estudiantes.estudiante", "estudiantes.apoderado"):
        campo.label_from_instance = lambda obj: privacidad.iniciales(str(obj))


class Formulario(FormularioBase, forms.Form):
    pass


class FormularioModelo(FormularioBase, forms.ModelForm):
    pass
