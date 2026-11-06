import re

from django.core.exceptions import ValidationError


class ComplejidadContrasenaValidator:
    """Exige letras y números en la contraseña."""

    def validate(self, password, user=None):
        if not re.search(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]", password) or not re.search(r"\d", password):
            raise ValidationError("La contraseña debe combinar letras y números.", code="password_complejidad")

    def get_help_text(self):
        return "La contraseña debe combinar letras y números."
