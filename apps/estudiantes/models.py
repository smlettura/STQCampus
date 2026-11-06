"""Ficha del estudiante, cursos, apoderados y promoción de fin de año (RF-01; pantallas «Estudiantes» del prototipo v1)."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone

from apps.core.validadores import (edad, formatear_rut, normalizar_rut, normalizar_telefono, validar_fecha_razonable,
                                   validar_no_futuro)

NIVELES = [
    ("PK", "Prekínder"), ("K", "Kínder"),
    ("1B", "1° Básico"), ("2B", "2° Básico"), ("3B", "3° Básico"), ("4B", "4° Básico"),
    ("5B", "5° Básico"), ("6B", "6° Básico"), ("7B", "7° Básico"), ("8B", "8° Básico"),
    ("1M", "1° Medio"), ("2M", "2° Medio"), ("3M", "3° Medio"), ("4M", "4° Medio"),
]
ORDEN_NIVEL = {codigo: i for i, (codigo, _) in enumerate(NIVELES)}
ABREVIATURA = {"PK": "PK", "K": "K", "1B": "1°B", "2B": "2°B", "3B": "3°B", "4B": "4°B", "5B": "5°B", "6B": "6°B",
               "7B": "7°B", "8B": "8°B", "1M": "1°M", "2M": "2°M", "3M": "3°M", "4M": "4°M"}
# Agrupaciones que usan las pantallas: cursos (prebásica/básica/media), anotaciones (ciclos) y conflictos (básica 1°–6°,
# media 7° básico–4° medio, como en el prototipo v1).
GRUPO_ENSENANZA = {"PK": "prebasica", "K": "prebasica", **{"%dB" % i: "basica" for i in range(1, 9)},
                   **{"%dM" % i: "media" for i in range(1, 5)}}
CICLO = {"PK": "prebasica", "K": "prebasica", **{"%dB" % i: "ciclo1" for i in range(1, 5)},
         **{"%dB" % i: "ciclo2" for i in range(5, 9)}, **{"%dM" % i: "media" for i in range(1, 5)}}
TRAMO_CONVIVENCIA = {"PK": "prebasica", "K": "prebasica", **{"%dB" % i: "basica" for i in range(1, 7)},
                     "7B": "media", "8B": "media", **{"%dM" % i: "media" for i in range(1, 5)}}


def orden_nivel():
    """Expresión para ordenar cursos de Prekínder a 4° Medio (los códigos no ordenan bien como texto)."""
    return Case(*[When(nivel=c, then=Value(i)) for c, i in ORDEN_NIVEL.items()], output_field=IntegerField())


class CursoQuerySet(models.QuerySet):
    def ordenados(self):
        return self.annotate(_orden=orden_nivel()).order_by("-anio_escolar", "_orden", "letra")


class Curso(models.Model):
    id = models.BigAutoField(primary_key=True, db_column="id_curso")
    sede = models.ForeignKey("core.Sede", on_delete=models.PROTECT, related_name="cursos", db_column="id_sede")
    nivel = models.CharField("nivel", max_length=20, choices=NIVELES)
    letra = models.CharField("letra", max_length=1)
    anio_escolar = models.PositiveSmallIntegerField("año escolar")
    profesor_jefe = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="cursos_jefatura", db_column="id_profesor_jefe")

    objects = CursoQuerySet.as_manager()

    class Meta:
        db_table = "curso"
        ordering = ["-anio_escolar", "nivel", "letra"]
        constraints = [
            models.UniqueConstraint(fields=["sede", "nivel", "letra", "anio_escolar"], name="uq_curso"),
            models.CheckConstraint(condition=Q(anio_escolar__gte=2000) & Q(anio_escolar__lte=2100), name="ck_curso_anio"),
        ]

    def __str__(self):
        return "%s %s %s" % (self.get_nivel_display(), self.letra, self.anio_escolar)

    @property
    def nombre(self):
        """Nombre corto, como en el prototipo: «5° Básico A»."""
        return "%s %s" % (self.get_nivel_display(), self.letra)

    @property
    def abreviatura(self):
        return ABREVIATURA.get(self.nivel, self.nivel)

    @property
    def orden(self):
        return ORDEN_NIVEL.get(self.nivel, 99)

    @property
    def grupo(self):
        return GRUPO_ENSENANZA.get(self.nivel, "")

    def nivel_siguiente(self):
        i = ORDEN_NIVEL.get(self.nivel)
        return NIVELES[i + 1][0] if i is not None and i + 1 < len(NIVELES) else None

    @property
    def nombre_nivel_siguiente(self):
        return dict(NIVELES).get(self.nivel_siguiente(), "")

    def clean(self):
        self.letra = (self.letra or "").strip().upper()
        if not self.letra.isalpha() or len(self.letra) != 1:
            raise ValidationError({"letra": "La letra del curso debe ser una sola letra (A-Z)."})
        if self.anio_escolar and not (2000 <= self.anio_escolar <= timezone.localdate().year + 1):
            raise ValidationError({"anio_escolar": "Año escolar fuera de rango."})
        if self.profesor_jefe_id and not self.profesor_jefe.tiene_rol("profesor_jefe"):
            raise ValidationError({"profesor_jefe": "El usuario seleccionado no tiene el rol de profesor jefe."})


def _limpio(texto):
    return " ".join((texto or "").split())


class EstudianteQuerySet(models.QuerySet):
    def activos(self, fecha=None):
        fecha = fecha or timezone.localdate()
        return self.filter(Q(fecha_egreso__isnull=True) | Q(fecha_egreso__gt=fecha))

    def inactivos(self, fecha=None):
        fecha = fecha or timezone.localdate()
        return self.filter(fecha_egreso__lte=fecha, tipo_salida="retiro")

    def egresados(self, fecha=None):
        fecha = fecha or timezone.localdate()
        return self.filter(fecha_egreso__lte=fecha, tipo_salida="egreso")

    def buscar(self, texto):
        texto = _limpio(texto)
        if not texto:
            return self
        # Cada palabra debe aparecer en algún nombre o apellido («martina pérez»); o bien el texto es parte del RUT.
        por_nombre = Q()
        for palabra in texto.split():
            por_nombre &= (Q(primer_nombre__icontains=palabra) | Q(segundo_nombre__icontains=palabra)
                           | Q(apellido_paterno__icontains=palabra) | Q(apellido_materno__icontains=palabra)
                           | Q(nombre_social__icontains=palabra))
        rut = texto.replace(".", "").replace(" ", "")
        return self.filter(Q(rut__icontains=rut) | por_nombre)


class Estudiante(models.Model):
    NECESIDADES = [("ninguna", "Sin NEE"), ("transitoria", "NEE transitoria"), ("permanente", "NEE permanente")]
    SALIDAS = [("retiro", "Retiro"), ("egreso", "Egreso")]

    id = models.BigAutoField(primary_key=True, db_column="id_estudiante")
    rut = models.CharField("RUT", max_length=12, unique=True)
    primer_nombre = models.CharField("primer nombre", max_length=40)
    segundo_nombre = models.CharField("segundo nombre", max_length=40, blank=True)
    apellido_paterno = models.CharField("apellido paterno", max_length=40)
    apellido_materno = models.CharField("apellido materno", max_length=40)
    nombre_social = models.CharField("nombre social", max_length=80, blank=True,
                                     help_text="Nombre con el que el estudiante pide ser tratado (Circular 812).")
    fecha_nacimiento = models.DateField("fecha de nacimiento", validators=[validar_no_futuro, validar_fecha_razonable])
    curso = models.ForeignKey(Curso, on_delete=models.PROTECT, related_name="estudiantes", db_column="id_curso")
    fecha_ingreso = models.DateField("fecha de ingreso", null=True, blank=True,
                                     validators=[validar_no_futuro, validar_fecha_razonable])
    necesidad_educativa = models.CharField("necesidad educativa", max_length=12, choices=NECESIDADES, default="ninguna")
    en_pie = models.BooleanField("PIE", default=False, help_text="Participa en el Programa de Integración Escolar.")
    prioritario = models.BooleanField("prioritario", default=False,
                                      help_text="Estudiante prioritario de la Subvención Escolar Preferencial (SEP).")
    matricula_condicional = models.BooleanField("matrícula condicional", default=False)
    fecha_egreso = models.DateField("fecha de egreso o retiro", null=True, blank=True, validators=[validar_fecha_razonable])
    tipo_salida = models.CharField("tipo de salida", max_length=8, choices=SALIDAS, blank=True)

    objects = EstudianteQuerySet.as_manager()

    class Meta:
        db_table = "estudiante"
        ordering = ["apellido_paterno", "apellido_materno", "primer_nombre"]
        constraints = [
            models.CheckConstraint(condition=Q(fecha_egreso__isnull=True) | Q(fecha_egreso__gt=models.F("fecha_nacimiento")),
                                   name="ck_estudiante_egreso"),
            models.CheckConstraint(condition=(Q(fecha_egreso__isnull=True) & Q(tipo_salida="")) |
                                   (Q(fecha_egreso__isnull=False) & ~Q(tipo_salida="")), name="ck_estudiante_salida"),
        ]

    def __str__(self):
        return "%s %s" % (self.nombres, self.apellidos)

    # Compatibilidad: nombres y apellidos completos como en el DER original.
    @property
    def nombres(self):
        return _limpio("%s %s" % (self.primer_nombre, self.segundo_nombre))

    @property
    def apellidos(self):
        return _limpio("%s %s" % (self.apellido_paterno, self.apellido_materno))

    @property
    def nombre_completo(self):
        return str(self)

    @property
    def nombre_lista(self):
        return "%s, %s" % (self.apellidos, self.nombres)

    @property
    def iniciales(self):
        return (self.primer_nombre[:1] + self.apellido_paterno[:1]).upper()

    @property
    def rut_formateado(self):
        return formatear_rut(self.rut)

    @property
    def edad(self):
        return edad(self.fecha_nacimiento) if self.fecha_nacimiento else None

    @property
    def activo(self):
        return self.fecha_egreso is None or self.fecha_egreso > timezone.localdate()

    @property
    def estado(self):
        if self.activo:
            return "activo"
        return "egresado" if self.tipo_salida == "egreso" else "inactivo"

    def get_estado_display(self):
        return {"activo": "Activo", "egresado": "Egresado", "inactivo": "Inactivo"}[self.estado]

    def apoderado_titular(self):
        vinculo = self.vinculos_apoderado.filter(es_titular=True).select_related("apoderado").first()
        return vinculo.apoderado if vinculo else None

    def clean(self):
        errores = {}
        if self.rut:
            try:
                self.rut = normalizar_rut(self.rut)
            except ValidationError as e:
                errores["rut"] = e.messages
        for campo in ("primer_nombre", "segundo_nombre", "apellido_paterno", "apellido_materno", "nombre_social"):
            setattr(self, campo, _limpio(getattr(self, campo)))
        for campo in ("primer_nombre", "apellido_paterno", "apellido_materno", "segundo_nombre"):
            valor = getattr(self, campo)
            if valor and not all(c.isalpha() or c in " '-." for c in valor):
                errores[campo] = "Use solo letras, espacios, apóstrofos o guiones."
        if self.fecha_nacimiento:
            anios = edad(self.fecha_nacimiento)
            if not 2 <= anios <= 25:
                errores["fecha_nacimiento"] = "La edad calculada (%d años) no corresponde a un estudiante escolar." % anios
            if self.fecha_ingreso and self.fecha_ingreso <= self.fecha_nacimiento:
                errores["fecha_ingreso"] = "La fecha de ingreso debe ser posterior a la fecha de nacimiento."
        if self.fecha_egreso and self.fecha_nacimiento and self.fecha_egreso <= self.fecha_nacimiento:
            errores["fecha_egreso"] = "La fecha de egreso debe ser posterior a la fecha de nacimiento."
        if self.fecha_egreso and not self.tipo_salida:
            errores["tipo_salida"] = "Indique si la salida corresponde a un retiro o a un egreso."
        if self.tipo_salida and not self.fecha_egreso:
            errores["fecha_egreso"] = "Indique la fecha de la salida."
        if self.en_pie and self.necesidad_educativa == "ninguna":
            errores["en_pie"] = "Un estudiante en el PIE debe tener una necesidad educativa transitoria o permanente."
        if errores:
            raise ValidationError(errores)


class Apoderado(models.Model):
    id = models.BigAutoField(primary_key=True, db_column="id_apoderado")
    rut = models.CharField("RUT", max_length=12, unique=True, null=True, blank=True,
                           help_text="Opcional, pero necesario para que el apoderado ejerza derechos ARCO+.")
    nombre_completo = models.CharField("nombre completo", max_length=120)
    telefono = models.CharField("teléfono", max_length=20, blank=True)
    correo = models.EmailField("correo", max_length=120, blank=True)

    class Meta:
        db_table = "apoderado"
        ordering = ["nombre_completo"]

    def __str__(self):
        return self.nombre_completo

    @property
    def rut_formateado(self):
        return formatear_rut(self.rut) if self.rut else ""

    def clean(self):
        errores = {}
        if self.rut:
            try:
                self.rut = normalizar_rut(self.rut)
            except ValidationError as e:
                errores["rut"] = e.messages
        else:
            self.rut = None
        try:
            self.telefono = normalizar_telefono(self.telefono)
        except ValidationError as e:
            errores["telefono"] = e.messages
        self.nombre_completo = _limpio(self.nombre_completo)
        if len(self.nombre_completo.split()) < 2:
            errores["nombre_completo"] = "Ingrese al menos un nombre y un apellido."
        if not self.telefono and not self.correo:
            errores["telefono"] = "Registre al menos un medio de contacto (teléfono o correo)."
        if errores:
            raise ValidationError(errores)


class EstudianteApoderado(models.Model):
    PARENTESCOS = [("madre", "Madre"), ("padre", "Padre"), ("abuela", "Abuela"), ("abuelo", "Abuelo"),
                   ("tia", "Tía"), ("tio", "Tío"), ("tutor", "Tutor legal"), ("otro", "Otro")]

    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name="vinculos_apoderado",
                                   db_column="id_estudiante")
    apoderado = models.ForeignKey(Apoderado, on_delete=models.CASCADE, related_name="vinculos_estudiante",
                                  db_column="id_apoderado")
    parentesco = models.CharField("parentesco", max_length=30, choices=PARENTESCOS)
    es_titular = models.BooleanField("apoderado titular", default=False)

    class Meta:
        db_table = "estudiante_apoderado"
        constraints = [models.UniqueConstraint(fields=["estudiante", "apoderado"], name="uq_estudiante_apoderado")]

    def __str__(self):
        return "%s — %s" % (self.estudiante, self.apoderado)

    def clean(self):
        # MySQL no admite restricciones únicas condicionales: la regla «un solo titular» se valida aquí.
        if self.es_titular and self.estudiante_id:
            otro = EstudianteApoderado.objects.filter(estudiante_id=self.estudiante_id, es_titular=True).exclude(pk=self.pk)
            if otro.exists():
                raise ValidationError({"es_titular": "El estudiante ya tiene un apoderado titular. Desmárquelo primero."})
        if self.estudiante_id and self.apoderado_id:
            if EstudianteApoderado.objects.filter(estudiante_id=self.estudiante_id,
                                                  apoderado_id=self.apoderado_id).exclude(pk=self.pk).exists():
                raise ValidationError("Este apoderado ya está vinculado al estudiante.")


# ---------------------------------------------------------------------------------------------- promoción de fin de año
class ProcesoPromocion(models.Model):
    """Promoción de fin de año en tres pasos: cursos terminales, revisión (repitentes) y procesamiento."""

    ESTADOS = [("borrador", "Borrador"), ("revisado", "Revisado"), ("procesado", "Procesado")]

    id = models.BigAutoField(primary_key=True, db_column="id_proceso")
    anio = models.PositiveSmallIntegerField("año escolar", unique=True)
    cursos_terminales = models.ManyToManyField(Curso, blank=True, related_name="+", db_table="proceso_curso_terminal",
                                               verbose_name="cursos terminales")
    estado = models.CharField("estado", max_length=10, choices=ESTADOS, default="borrador")
    fecha_proceso = models.DateTimeField("fecha de procesamiento", null=True, blank=True)
    procesado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name="+", db_column="id_procesado_por")

    class Meta:
        db_table = "proceso_promocion"
        ordering = ["-anio"]

    def __str__(self):
        return "Promoción %s" % self.anio

    @property
    def procesado(self):
        return self.estado == "procesado"


class PromocionEstudiante(models.Model):
    RESULTADOS = [("promovido", "Promovido"), ("repite", "Repite"), ("egresa", "Egresa")]

    id = models.BigAutoField(primary_key=True, db_column="id_promocion")
    proceso = models.ForeignKey(ProcesoPromocion, on_delete=models.CASCADE, related_name="resultados",
                                db_column="id_proceso")
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name="promociones",
                                   db_column="id_estudiante")
    curso_origen = models.ForeignKey(Curso, on_delete=models.PROTECT, related_name="+", db_column="id_curso_origen")
    curso_destino = models.ForeignKey(Curso, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
                                      db_column="id_curso_destino")
    resultado = models.CharField("resultado", max_length=10, choices=RESULTADOS)

    class Meta:
        db_table = "promocion_estudiante"
        constraints = [models.UniqueConstraint(fields=["proceso", "estudiante"], name="uq_promocion_estudiante")]
