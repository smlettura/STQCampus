"""Seudonimización antes de que el texto salga de AWS hacia el equipo propio, y reidentificación al volver (RNF-11).

- Nombres del estudiante, apoderados y profesionales → [ESTUDIANTE], [APODERADO_1], [PROFESIONAL_1]…
- RUT, correos, teléfonos y direcciones → se eliminan ([RUT], [CORREO], [TELEFONO], [DIRECCION]).
- Fecha de nacimiento → edad. Curso, sede e instituciones → [CURSO], [SEDE], [ESTABLECIMIENTO].
- Si después de reemplazar queda algún identificador conocido, se lanza SeudonimizacionIncompleta y no sale nada.

La comparación no distingue mayúsculas ni tildes («Pérez» también reemplaza «perez»). Ante la duda se reemplaza de más:
un nombre que coincide con una palabra común también se cambia por el marcador.
"""
import json
import re
import unicodedata

from django.conf import settings

GENERICOS = [
    ("[RUT]", re.compile(r"(?<![\w.])\d{1,2}\.?\d{3}\.?\d{3}\s*-\s*[\dkK](?!\w)")),
    ("[CORREO]", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("[TELEFONO]", re.compile(r"(?<!\d)(?:\+?56[\s-]?)?(?:9[\s-]?\d{4}[\s-]?\d{4}|[2-9]\d[\s-]?\d{3}[\s-]?\d{4})(?!\d)")),
    ("[DIRECCION]", re.compile(r"\b(?:calle|avenida|av\.|pasaje|psje\.|villa|poblaci[oó]n|condominio)\s+[^\n,;]{2,50}?\s+#?\d{1,5}\b",
                               re.IGNORECASE)),
]
ELIMINADOS = {"[RUT]", "[CORREO]", "[TELEFONO]", "[DIRECCION]"}
_VOCALES = {"a": "aáà", "e": "eéè", "i": "iíì", "o": "oóò", "u": "uúùü"}


class SeudonimizacionIncompleta(Exception):
    """Quedó un dato identificable después de seudonimizar: la solicitud se bloquea."""


def normalizar(texto):
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return sin_tildes.lower()


def _patron(frase):
    """Expresión que encuentra la frase sin distinguir mayúsculas ni tildes, como palabra completa."""
    partes = []
    for c in normalizar(frase):
        if c in _VOCALES:
            partes.append("[%s]" % _VOCALES[c])
        elif c.isspace():
            partes.append(r"\s+")
        else:
            partes.append(re.escape(c))
    return re.compile(r"(?<!\w)" + "".join(partes) + r"(?!\w)", re.IGNORECASE)


def _tokens(nombre):
    return [t for t in re.split(r"[\s\-]+", nombre or "") if len(t) >= 3]


def _edad_en(fecha, hoy):
    return hoy.year - fecha.year - ((hoy.month, hoy.day) < (fecha.month, fecha.day))


class Seudonimizador:
    def __init__(self, estudiante, profesionales=(), hoy=None):
        from django.utils import timezone
        self.hoy = hoy or timezone.localdate()
        self.reglas = []          # (patrón, marcador), se aplican de la frase más larga a la más corta
        self.mapa = {}            # marcador → texto con que se reidentifica
        self.identificadores = set()   # textos normalizados que no pueden quedar en la salida
        e = estudiante
        nombre_mostrar = e.nombre_social or ("%s %s" % (e.primer_nombre, e.apellido_paterno))
        frases = {e.nombre_social, "%s %s" % (e.nombres, e.apellidos), "%s %s %s" % (e.primer_nombre, e.apellido_paterno,
                  e.apellido_materno), "%s %s" % (e.primer_nombre, e.apellido_paterno), e.nombres, e.apellidos}
        for x in (e.primer_nombre, e.segundo_nombre, e.apellido_paterno, e.apellido_materno, e.nombre_social):
            frases.update(_tokens(x))
        self._agregar(frases, "[ESTUDIANTE]", nombre_mostrar)
        self._fecha_nacimiento(e.fecha_nacimiento)
        self.identificadores.update(self._digitos(e.rut))
        for i, vinculo in enumerate(e.vinculos_apoderado.select_related("apoderado").order_by("-es_titular", "id"), 1):
            a = vinculo.apoderado
            self._agregar({a.nombre_completo, *_tokens(a.nombre_completo)}, "[APODERADO_%d]" % i, a.nombre_completo)
            self.identificadores.update(self._digitos(a.rut) | self._digitos(a.telefono))
            if a.correo:
                self.identificadores.add(normalizar(a.correo))
        vistos = []
        for p in profesionales:
            if p is not None and p.pk not in vistos and getattr(p, "nombre_completo", ""):
                vistos.append(p.pk)
                self._agregar({p.nombre_completo, *_tokens(p.nombre_completo)}, "[PROFESIONAL_%d]" % len(vistos),
                              p.nombre_completo)
        curso = e.curso
        self._agregar(self._variantes_curso(curso), "[CURSO]", curso.nombre)
        self._agregar({curso.sede.nombre}, "[SEDE]", curso.sede.nombre)
        instituciones = [x.strip() for x in getattr(settings, "IA_INSTITUCIONES", []) if x.strip()]
        if instituciones:
            self._agregar(set(instituciones), "[ESTABLECIMIENTO]", instituciones[0])
        self.reglas.sort(key=lambda r: -len(r[2]))

    # ------------------------------------------------------------------ construcción
    def _agregar(self, frases, marcador, valor):
        self.mapa[marcador] = valor
        for f in {f.strip() for f in frases if f and f.strip()}:
            if len(normalizar(f)) < 3:
                continue
            self.reglas.append((_patron(f), marcador, normalizar(f)))
            self.identificadores.add(normalizar(f))

    @staticmethod
    def _digitos(valor):
        d = re.sub(r"\D", "", valor or "")
        return {d} if len(d) >= 7 else set()

    @staticmethod
    def _variantes_curso(curso):
        variantes = {curso.nombre}
        m = re.match(r"(\d)([BM])$", curso.nivel or "")
        if m:
            n, nivel = m.groups()
            palabra = "básico" if nivel == "B" else "medio"
            variantes |= {"%s° %s %s" % (n, palabra, curso.letra), "%s°%s" % (n, curso.letra), "%s° %s" % (n, curso.letra),
                          "%s°%s %s" % (n, nivel, curso.letra), "%s %s %s" % (n, palabra, curso.letra)}
        return variantes

    def _fecha_nacimiento(self, fecha):
        if not fecha:
            return
        edad = "[EDAD: %d años]" % _edad_en(fecha, self.hoy)
        for f in {fecha.strftime("%d/%m/%Y"), fecha.strftime("%d-%m-%Y"), fecha.strftime("%Y-%m-%d"),
                  "%d/%d/%d" % (fecha.day, fecha.month, fecha.year)}:
            self.reglas.append((re.compile(re.escape(f)), edad, f))
            self.identificadores.add(f)

    # ------------------------------------------------------------------ uso
    def aplicar(self, texto):
        for marcador, patron in GENERICOS:
            texto = patron.sub(marcador, texto)
        for patron, marcador, _ in self.reglas:
            texto = patron.sub(marcador, texto)
        self.verificar(texto)
        return texto

    def verificar(self, texto):
        plano = normalizar(texto)
        solo_digitos = re.sub(r"\D", "", texto)
        for marcador, patron in GENERICOS:
            if patron.search(texto):
                raise SeudonimizacionIncompleta("Quedó un dato del tipo %s." % marcador)
        for ident in self.identificadores:
            if ident.isdigit():
                if ident in solo_digitos:
                    raise SeudonimizacionIncompleta("Quedó un número identificable.")
            elif re.search(r"(?<!\w)" + re.escape(ident) + r"(?!\w)", plano):
                raise SeudonimizacionIncompleta("Quedó un nombre o dato identificable.")

    def correspondencia(self):
        return json.dumps(self.mapa, ensure_ascii=False)


def reidentificar(texto, correspondencia):
    """Reemplaza los marcadores por los datos reales. Los datos eliminados (RUT, correo…) no se restituyen."""
    mapa = json.loads(correspondencia or "{}")
    for marcador in sorted(mapa, key=len, reverse=True):
        texto = texto.replace(marcador, mapa[marcador])
    return texto
