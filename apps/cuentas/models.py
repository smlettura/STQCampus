"""Usuarios, roles y permisos (RF-09, RNF-02). Un usuario puede ejercer más de un rol, acotado a una sede si corresponde."""
from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.campos import TextoCifrado


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, correo, nombre_completo="", password=None, **extra):
        if not correo:
            raise ValueError("El correo es obligatorio.")
        usuario = self.model(correo=self.normalize_email(correo).lower(), nombre_completo=nombre_completo, **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, correo, password=None, **extra):
        """Crea un usuario con el rol Administrador (gestión de cuentas, sin acceso a contenido clínico)."""
        usuario = self.create_user(correo, extra.pop("nombre_completo", "Administrador"), password, **extra)
        rol = Rol.objects.filter(codigo="administrador").first()
        if rol:
            UsuarioRol.objects.create(usuario=usuario, rol=rol)
        return usuario


class Usuario(AbstractBaseUser):
    id = models.BigAutoField(primary_key=True, db_column="id_usuario")
    correo = models.EmailField("correo", max_length=120, unique=True)
    nombre_completo = models.CharField("nombre completo", max_length=120)
    password = models.CharField("contraseña", max_length=255, db_column="hash_contrasena")
    secreto_totp = TextoCifrado("secreto del segundo factor", null=True, blank=True, editable=False)
    mfa_activo = models.BooleanField("segundo factor activo", default=False)
    activo = models.BooleanField("activo", default=True)
    last_login = models.DateTimeField("último acceso", null=True, blank=True, db_column="ultimo_acceso")
    # Datos del perfil (pantalla «Mi perfil» del prototipo v1)
    telefono = models.CharField("teléfono", max_length=20, blank=True)
    especialidad = models.CharField("especialidad o área", max_length=80, blank=True)
    fecha_alta = models.DateTimeField("fecha de ingreso", default=timezone.now, editable=False)
    contrasena_actualizada = models.DateTimeField("último cambio de contraseña", null=True, blank=True, editable=False)
    cambio_contrasena_pendiente = models.BooleanField(
        "primer ingreso pendiente", default=False,
        help_text="Obliga a cambiar la contraseña entregada por el administrador en el primer ingreso.")

    objects = UsuarioManager()

    USERNAME_FIELD = "correo"
    EMAIL_FIELD = "correo"
    REQUIRED_FIELDS = ["nombre_completo"]

    class Meta:
        db_table = "usuario"
        ordering = ["nombre_completo"]
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def __str__(self):
        return self.nombre_completo or self.correo

    @property
    def is_active(self):
        return self.activo

    @property
    def iniciales(self):
        partes = (self.nombre_completo or self.correo).split()
        return "".join(p[0] for p in partes[:2]).upper()

    def set_password(self, raw_password):
        super().set_password(raw_password)
        if raw_password is not None:
            self.contrasena_actualizada = timezone.now()

    def clean(self):
        super().clean()
        self.correo = (self.correo or "").strip().lower()
        if Usuario.objects.exclude(pk=self.pk).filter(correo__iexact=self.correo).exists():
            raise ValidationError({"correo": "Ya existe un usuario con este correo."})
        if self.telefono:
            from apps.core.validadores import normalizar_telefono
            try:
                self.telefono = normalizar_telefono(self.telefono)
            except ValidationError as e:
                raise ValidationError({"telefono": e.messages})

    # --------------------------------------------------------------- roles y permisos
    def asignaciones_vigentes(self, fecha=None):
        return self.asignaciones.vigentes(fecha).select_related("rol", "sede")

    def codigos_rol(self):
        if not hasattr(self, "_cache_roles"):
            self._cache_roles = frozenset(self.asignaciones_vigentes().values_list("rol__codigo", flat=True))
        return self._cache_roles

    def codigos_permiso(self):
        if not hasattr(self, "_cache_permisos"):
            roles = self.asignaciones_vigentes().values("rol_id")
            self._cache_permisos = frozenset(
                Permiso.objects.filter(rol_permisos__rol_id__in=roles).values_list("codigo", flat=True))
        return self._cache_permisos

    def tiene_permiso(self, *codigos):
        return self.is_authenticated and self.activo and any(c in self.codigos_permiso() for c in codigos)

    def tiene_rol(self, *codigos):
        return any(c in self.codigos_rol() for c in codigos)

    def requiere_2fa(self):
        return self.mfa_activo or any(r in settings.ROLES_CON_2FA for r in self.codigos_rol())

    def limpiar_cache(self):
        for attr in ("_cache_roles", "_cache_permisos"):
            if hasattr(self, attr):
                delattr(self, attr)


class Rol(models.Model):
    id = models.BigAutoField(primary_key=True, db_column="id_rol")
    codigo = models.SlugField("código", max_length=40, unique=True)
    nombre = models.CharField("nombre", max_length=40, unique=True)
    descripcion = models.CharField("descripción", max_length=160, blank=True)

    class Meta:
        db_table = "rol"
        ordering = ["nombre"]
        verbose_name = "rol"
        verbose_name_plural = "roles"

    def __str__(self):
        return self.nombre


class Permiso(models.Model):
    id = models.BigAutoField(primary_key=True, db_column="id_permiso")
    codigo = models.CharField("código", max_length=60, unique=True)
    descripcion = models.CharField("descripción", max_length=160)

    class Meta:
        db_table = "permiso"
        ordering = ["codigo"]

    def __str__(self):
        return self.codigo


class RolPermiso(models.Model):
    rol = models.ForeignKey(Rol, on_delete=models.CASCADE, related_name="rol_permisos", db_column="id_rol")
    permiso = models.ForeignKey(Permiso, on_delete=models.CASCADE, related_name="rol_permisos", db_column="id_permiso")

    class Meta:
        db_table = "rol_permiso"
        constraints = [models.UniqueConstraint(fields=["rol", "permiso"], name="uq_rol_permiso")]


class UsuarioRolQuerySet(models.QuerySet):
    def vigentes(self, fecha=None):
        fecha = fecha or timezone.localdate()
        return self.filter(vigente_desde__lte=fecha).filter(Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=fecha))


class UsuarioRol(models.Model):
    id = models.BigAutoField(primary_key=True, db_column="id_usuario_rol")
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="asignaciones", db_column="id_usuario")
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, related_name="asignaciones", db_column="id_rol")
    sede = models.ForeignKey("core.Sede", on_delete=models.PROTECT, null=True, blank=True, related_name="asignaciones",
                             db_column="id_sede", help_text="Déjelo vacío si el rol aplica a todas las sedes.")
    vigente_desde = models.DateField("vigente desde", default=timezone.localdate)
    vigente_hasta = models.DateField("vigente hasta", null=True, blank=True)

    objects = UsuarioRolQuerySet.as_manager()

    class Meta:
        db_table = "usuario_rol"
        ordering = ["usuario__nombre_completo", "rol__nombre"]
        constraints = [
            models.CheckConstraint(condition=Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=models.F("vigente_desde")),
                                   name="ck_usuario_rol_vigencia"),
        ]

    def __str__(self):
        return "%s — %s%s" % (self.usuario, self.rol, " (%s)" % self.sede if self.sede else "")

    ROLES_POR_SEDE = ("inspectoria",)

    def clean(self):
        if self.rol_id and self.rol.codigo in self.ROLES_POR_SEDE and not self.sede_id:
            raise ValidationError({"sede": "Este rol se asigna para una sede específica."})
        if self.vigente_hasta and self.vigente_desde and self.vigente_hasta < self.vigente_desde:
            raise ValidationError({"vigente_hasta": "La fecha de término no puede ser anterior a la de inicio."})
        if self.usuario_id and self.rol_id:
            solapadas = UsuarioRol.objects.filter(usuario_id=self.usuario_id, rol_id=self.rol_id, sede_id=self.sede_id)
            solapadas = solapadas.exclude(pk=self.pk).filter(
                Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=self.vigente_desde))
            if self.vigente_hasta:
                solapadas = solapadas.filter(vigente_desde__lte=self.vigente_hasta)
            if solapadas.exists():
                raise ValidationError("El usuario ya tiene este rol vigente en ese período y sede.")
