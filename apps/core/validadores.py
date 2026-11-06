"""Validadores reutilizables: RUT chileno, teléfono, fechas y archivos adjuntos."""
import datetime
import re
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.deconstruct import deconstructible

# ------------------------------------------------------------------ RUT (módulo 11)
_RUT_RE = re.compile(r"^(\d{1,3}(?:\.?\d{3}){1,2})-?([\dkK])$")


def calcular_dv(numero):
    """Dígito verificador del RUT según el algoritmo de módulo 11."""
    suma, factor = 0, 2
    for digito in reversed(str(numero)):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - (suma % 11)
    return {11: "0", 10: "K"}.get(resto, str(resto))


def normalizar_rut(valor):
    """Devuelve el RUT en formato 12345678-9 (sin puntos, DV en mayúscula) o lanza ValidationError."""
    if valor is None:
        raise ValidationError("Ingrese un RUT.", code="rut_vacio")
    texto = str(valor).strip().replace(" ", "")
    m = _RUT_RE.match(texto)
    if not m:
        raise ValidationError("Formato de RUT inválido. Use 12.345.678-9 o 12345678-9.", code="rut_formato")
    numero = int(m.group(1).replace(".", ""))
    dv = m.group(2).upper()
    if numero < 1_000_000:
        raise ValidationError("El número de RUT es demasiado bajo.", code="rut_rango")
    if calcular_dv(numero) != dv:
        raise ValidationError("El dígito verificador del RUT no es válido.", code="rut_dv")
    return "%d-%s" % (numero, dv)


def validar_rut(valor):
    normalizar_rut(valor)


def formatear_rut(rut):
    """12345678-9 -> 12.345.678-9 (solo para mostrar)."""
    try:
        numero, dv = rut.split("-")
        return "{:,}".format(int(numero)).replace(",", ".") + "-" + dv
    except (ValueError, AttributeError):
        return rut


# ------------------------------------------------------------------ teléfono chileno
def normalizar_telefono(valor):
    """Acepta 9XXXXXXXX, +56 9 XXXX XXXX o fijos de 9 dígitos. Devuelve +569XXXXXXXX."""
    if not valor:
        return ""
    digitos = re.sub(r"[\s\-().]", "", str(valor))
    if digitos.startswith("+56"):
        digitos = digitos[3:]
    elif digitos.startswith("56") and len(digitos) == 11:
        digitos = digitos[2:]
    if not digitos.isdigit() or len(digitos) != 9:
        raise ValidationError("El teléfono debe tener 9 dígitos (por ejemplo, +56 9 1234 5678).", code="telefono")
    return "+56" + digitos


# ------------------------------------------------------------------ fechas
TOLERANCIA_RELOJ = datetime.timedelta(minutes=5)


def validar_no_futuro(valor):
    if valor is None:
        return
    if isinstance(valor, datetime.datetime):
        if valor > timezone.now() + TOLERANCIA_RELOJ:
            raise ValidationError("La fecha y hora no puede estar en el futuro.", code="futuro")
    elif valor > timezone.localdate():
        raise ValidationError("La fecha no puede estar en el futuro.", code="futuro")


def validar_fecha_razonable(valor):
    if valor is None:
        return
    anio = valor.year
    if anio < 1900 or anio > timezone.localdate().year + 20:
        raise ValidationError("La fecha está fuera del rango permitido.", code="rango_fecha")


def sumar_anios(fecha, anios):
    """Suma años respetando el 29 de febrero."""
    try:
        return fecha.replace(year=fecha.year + anios)
    except ValueError:
        return fecha.replace(year=fecha.year + anios, day=28)


def inicio_del_dia(fecha):
    """Datetime consciente de la zona horaria para el comienzo del día local. Se usa en lugar de los filtros __date,
    que en MySQL requieren tablas de zonas horarias cargadas."""
    return timezone.make_aware(datetime.datetime.combine(fecha, datetime.time.min))


def edad(fecha_nacimiento, referencia=None):
    referencia = referencia or timezone.localdate()
    return referencia.year - fecha_nacimiento.year - (
        (referencia.month, referencia.day) < (fecha_nacimiento.month, fecha_nacimiento.day))


# ------------------------------------------------------------------ texto
@deconstructible
class TextoMinimoValidator:
    """Exige un largo mínimo de texto útil (sin contar espacios al inicio y al final)."""

    def __init__(self, minimo):
        self.minimo = minimo

    def __call__(self, valor):
        if valor is not None and len(str(valor).strip()) < self.minimo:
            raise ValidationError("Escriba al menos %d caracteres." % self.minimo, code="texto_corto")

    def __eq__(self, otro):
        return isinstance(otro, TextoMinimoValidator) and otro.minimo == self.minimo


validar_texto_minimo = TextoMinimoValidator


# ------------------------------------------------------------------ archivos adjuntos (RF-04: PDF y fotografías)
FIRMAS_PERMITIDAS = {
    ".pdf": (b"%PDF-",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
}
# Documentos de Office (evidencias del plan de gestión e importación de Excel): son archivos ZIP con [Content_Types].xml.
FIRMAS_OFFICE = {".docx": (b"PK\x03\x04",), ".pptx": (b"PK\x03\x04",), ".xlsx": (b"PK\x03\x04",)}
FIRMAS_EVIDENCIA = {**FIRMAS_PERMITIDAS, **FIRMAS_OFFICE}
FIRMAS_EXCEL = {".xlsx": FIRMAS_OFFICE[".xlsx"]}
TIPOS_MIME = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
              ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
              ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
              ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
NOMBRES_TIPO = {".pdf": "PDF", ".jpg": "JPG", ".jpeg": "JPG", ".png": "PNG", ".docx": "Word", ".pptx": "PowerPoint",
                ".xlsx": "Excel"}


def validar_adjunto(archivo, permitidas=None):
    """Comprueba tamaño, extensión y firma real del archivo (no basta con la extensión)."""
    permitidas = permitidas or FIRMAS_PERMITIDAS
    maximo = settings.ADJUNTO_MAX_MB * 1024 * 1024
    if archivo.size == 0:
        raise ValidationError("El archivo está vacío.", code="archivo_vacio")
    if archivo.size > maximo:
        raise ValidationError("El archivo supera el máximo de %d MB." % settings.ADJUNTO_MAX_MB, code="archivo_grande")
    extension = Path(archivo.name).suffix.lower()
    if extension not in permitidas:
        nombres = list(dict.fromkeys(NOMBRES_TIPO[e] for e in permitidas))
        texto = nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " o " + nombres[-1]
        raise ValidationError("Solo se permiten archivos %s." % texto, code="archivo_tipo")
    archivo.seek(0)
    cabecera = archivo.read(16)
    archivo.seek(0)
    valido = any(cabecera.startswith(f) for f in permitidas[extension])
    if valido and extension in FIRMAS_OFFICE:
        import zipfile
        try:
            with zipfile.ZipFile(archivo) as z:
                valido = "[Content_Types].xml" in z.namelist()
        except zipfile.BadZipFile:
            valido = False
        archivo.seek(0)
    if not valido:
        raise ValidationError("El contenido del archivo no corresponde a un %s válido." % NOMBRES_TIPO[extension],
                              code="archivo_firma")


def nombre_archivo_seguro(nombre):
    base = Path(nombre).name
    base = re.sub(r"[^\w.\- ]", "_", base, flags=re.UNICODE).strip()
    return base[:150] or "archivo"
