"""Campo de modelo que guarda texto cifrado con AES-256-GCM y lo entrega descifrado a la aplicación."""
from base64 import b64encode

from django import forms
from django.db import models
from django.utils.text import capfirst

from .cifrado import cifrar_texto, descifrar_texto


class TextoCifrado(models.BinaryField):
    description = "Texto cifrado a nivel de campo (AES-256-GCM)"

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("editable", True)
        super().__init__(*args, **kwargs)

    def contexto(self):
        return "%s.%s" % (self.model._meta.db_table, self.column)

    def get_default(self):
        if self.has_default():
            return super().get_default()
        return None if self.null else ""

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        value = bytes(value)
        return descifrar_texto(value, self.contexto()) if value else ""

    def to_python(self, value):
        if value is None or isinstance(value, str):
            return value
        if isinstance(value, (bytes, bytearray, memoryview)):
            value = bytes(value)
            return descifrar_texto(value, self.contexto()) if value else ""
        return str(value)

    def get_prep_value(self, value):
        if value is None:
            return None
        if isinstance(value, (bytes, bytearray, memoryview)):   # ya viene cifrado (p. ej., rotación de claves)
            return bytes(value)
        return cifrar_texto(str(value), self.contexto())

    def value_to_string(self, obj):
        valor = self.value_from_object(obj)
        return "" if valor is None else b64encode(self.get_prep_value(valor)).decode("ascii")

    def formfield(self, **kwargs):
        defaults = {"form_class": forms.CharField, "widget": forms.Textarea(attrs={"rows": 5}),
                    "required": not self.blank, "label": capfirst(self.verbose_name), "help_text": self.help_text,
                    "strip": True}
        defaults.update(kwargs)
        form_class = defaults.pop("form_class")
        return form_class(**defaults)
