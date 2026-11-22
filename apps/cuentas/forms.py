from django import forms
from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, PasswordResetForm, SetPasswordForm
from django.core.cache import cache
from django.core.exceptions import ValidationError

from apps.core.formularios import FormularioBase, FormularioModelo, Formulario

from .models import Usuario, UsuarioRol


def _clave_bloqueo(correo):
    return "login_fallido:%s" % (correo or "").strip().lower()


class IngresoForm(FormularioBase, AuthenticationForm):
    """Inicio de sesión con bloqueo temporal tras intentos fallidos consecutivos."""

    username = forms.EmailField(label="Correo", widget=forms.EmailInput(attrs={
        "autofocus": True, "autocomplete": "username", "placeholder": "nombre@colegiostq.cl"}))
    password = forms.CharField(label="Contraseña", strip=False, widget=forms.PasswordInput(attrs={
        "autocomplete": "current-password", "placeholder": "••••••••"}))
    recordar = forms.BooleanField(label="Recordarme", required=False,
                                  help_text="Guarda solo su correo en este equipo; la contraseña siempre se pide.")
    error_messages = {
        "invalid_login": "Correo o contraseña incorrectos.",
        "inactive": "La cuenta está desactivada. Contacte al administrador.",
    }

    def clean(self):
        correo = self.cleaned_data.get("username")
        clave = _clave_bloqueo(correo)
        if cache.get(clave, 0) >= settings.LOGIN_MAX_INTENTOS:
            raise ValidationError("Demasiados intentos fallidos. La cuenta queda bloqueada por %d minutos."
                                  % settings.LOGIN_BLOQUEO_MINUTOS, code="bloqueada")
        try:
            datos = super().clean()
        except ValidationError:
            intentos = cache.get(clave, 0) + 1
            cache.set(clave, intentos, settings.LOGIN_BLOQUEO_MINUTOS * 60)
            raise
        cache.delete(clave)
        return datos


class CodigoForm(Formulario):
    codigo = forms.CharField(label="Código de 6 dígitos", max_length=7,
                             widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "one-time-code",
                                                           "autofocus": True, "pattern": r"\d{3}\s?\d{3}"}))

    def clean_codigo(self):
        codigo = self.cleaned_data["codigo"].replace(" ", "")
        if not codigo.isdigit() or len(codigo) != 6:
            raise ValidationError("El código tiene 6 dígitos.")
        return codigo


class UsuarioCrearForm(FormularioModelo):
    password1 = forms.CharField(label="Contraseña inicial", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
                                help_text=password_validation.password_validators_help_text_html())
    password2 = forms.CharField(label="Repita la contraseña", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    class Meta:
        model = Usuario
        fields = ["nombre_completo", "correo"]

    def clean_correo(self):
        correo = self.cleaned_data["correo"].strip().lower()
        if Usuario.objects.filter(correo__iexact=correo).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Ya existe un usuario con este correo.")
        return correo

    def clean_nombre_completo(self):
        nombre = " ".join(self.cleaned_data["nombre_completo"].split())
        if len(nombre.split()) < 2:
            raise ValidationError("Ingrese nombre y apellido.")
        return nombre

    def clean(self):
        datos = super().clean()
        p1, p2 = datos.get("password1"), datos.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        if p1:
            usuario = Usuario(correo=datos.get("correo", ""), nombre_completo=datos.get("nombre_completo", ""))
            try:
                password_validation.validate_password(p1, usuario)
            except ValidationError as e:
                self.add_error("password1", e)
        return datos

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.set_password(self.cleaned_data["password1"])
        usuario.cambio_contrasena_pendiente = True       # debe cambiarla en su primer ingreso
        if commit:
            usuario.save()
        return usuario


class UsuarioEditarForm(FormularioModelo):
    class Meta:
        model = Usuario
        fields = ["nombre_completo", "correo", "activo"]

    def __init__(self, *args, editor=None, **kwargs):
        self.editor = editor
        super().__init__(*args, **kwargs)

    def clean_correo(self):
        correo = self.cleaned_data["correo"].strip().lower()
        if Usuario.objects.filter(correo__iexact=correo).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Ya existe un usuario con este correo.")
        return correo

    def clean_activo(self):
        activo = self.cleaned_data["activo"]
        if not activo and self.editor and self.editor.pk == self.instance.pk:
            raise ValidationError("No puede desactivar su propia cuenta.")
        if not activo and self.instance.tiene_rol("administrador") and not otros_administradores(self.instance).exists():
            raise ValidationError("Debe quedar al menos un administrador activo.")
        return activo


def otros_administradores(usuario):
    return Usuario.objects.filter(activo=True, asignaciones__in=UsuarioRol.objects.vigentes().filter(
        rol__codigo="administrador")).exclude(pk=usuario.pk).distinct()


class AsignacionRolForm(FormularioModelo):
    class Meta:
        model = UsuarioRol
        fields = ["rol", "sede", "vigente_desde", "vigente_hasta"]

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if usuario is not None:
            self.instance.usuario = usuario


class CambioContrasenaForm(FormularioBase, PasswordChangeForm):
    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.cambio_contrasena_pendiente = False
        if commit:
            usuario.save()
        return usuario


class PerfilForm(FormularioModelo):
    """«Actualizar información» de Mi perfil: datos de contacto que la propia usuaria puede mantener."""

    class Meta:
        model = Usuario
        fields = ["telefono", "especialidad"]
        widgets = {"telefono": forms.TextInput(attrs={"placeholder": "+56 9 …", "autocomplete": "tel"})}

    def clean_especialidad(self):
        return " ".join(self.cleaned_data["especialidad"].split())


class RestablecerContrasenaForm(FormularioBase, PasswordResetForm):
    email = forms.EmailField(label="Correo", max_length=254,
                             widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True,
                                                            "placeholder": "nombre@colegiostq.cl"}))

    def get_users(self, email):
        # El modelo usa «correo» y «activo»; se omiten las cuentas sin contraseña utilizable.
        for usuario in Usuario.objects.filter(correo__iexact=(email or "").strip(), activo=True):
            if usuario.has_usable_password():
                yield usuario


class NuevaContrasenaForm(FormularioBase, SetPasswordForm):
    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.cambio_contrasena_pendiente = False
        if commit:
            usuario.save()
        return usuario
