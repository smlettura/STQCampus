"""
apps/ia/guardas.py -- Guardianes de limites del modulo de IA (STQCampus).

Dos capas de codigo que NO dependen de que el modelo obedezca el prompt:

  * guardian de ENTRADA: detecta peticiones que el modulo no puede atender
    (diagnosticar, clasificar riesgo, decidir PIE, medicar, inferir emociones, inventar datos)
    y neutraliza instrucciones inyectadas dentro de las notas.
  * guardian de SALIDA: revisa lo que escribio el modelo y detecta contenido fuera de limites
    (nivel de riesgo, recomendacion sobre PIE, medicacion, diagnostico nuevo, emocion inferida).

Es un filtro de patrones: reduce el riesgo, no lo elimina. Siempre queda la validacion humana (RF-18).
Solo biblioteca estandar.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Codigos de limite (se usan en auditoria y en las pruebas)
DIAGNOSTICO = "DIAGNOSTICO"
RIESGO = "NIVEL_DE_RIESGO"
PIE = "DECISION_PIE"
MEDICACION = "MEDICACION"
EMOCION = "EMOCION_INFERIDA"
SANCION = "SANCION"
INVENCION = "INVENCION"
INYECCION = "INSTRUCCION_INYECTADA"
CONDICION = "CONDICION_NO_PERMITIDA"
SECCION = "SECCION_NO_PEDIDA"

DESCRIPCION = {
    DIAGNOSTICO: "diagnosticar o sugerir un diagnostico",
    RIESGO: "clasificar o estimar un nivel de riesgo",
    PIE: "decidir o recomendar ingreso, egreso o continuidad en el PIE",
    MEDICACION: "recomendar medicamentos o tratamientos",
    EMOCION: "inferir estados emocionales o rasgos",
    SANCION: "proponer sanciones o medidas disciplinarias",
    INVENCION: "inventar informacion que no esta en las notas",
    INYECCION: "una instruccion dirigida al asistente dentro de las notas",
    CONDICION: "una condicion que no es de formato",
    SECCION: "agregar una seccion que no se pidio",
}


def _n(texto: str) -> str:
    """Minusculas y sin tildes, para comparar."""
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


@dataclass(frozen=True)
class Hallazgo:
    codigo: str
    fragmento: str

    def __str__(self) -> str:
        return f"{DESCRIPCION[self.codigo]} («{self.fragmento.strip()[:90]}»)"


# --------------------------------------------------------------------------- #
# Guardian de ENTRADA
# --------------------------------------------------------------------------- #
# Patrones sobre texto normalizado (sin tildes). Buscan PETICIONES, no menciones:
# "diagnostico registrado por la psicologa" no dispara; "que diagnostico tiene" si.
_PETICIONES = {
    DIAGNOSTICO: [
        r"\bque diagnostico\b", r"\bdiagnostic[ao]\w*\s+(a|al|de)?\s*\[?estudiante",
        r"\b(diagnostica|diagnostique)\s+(a |al |el caso|lo |su )", r"\bdiagnosticar\b", r"\b(diagnostico probable|posible diagnostico)\b",
        r"\b(cumple|cumpliria|presenta)\s+criterios\b", r"\bpodria tener\b.{0,40}\b(tdah|ansiedad|depresion|trastorno|autismo|tea)\b",
        r"\b(hay|existe|sospech\w+)\b.{0,25}\b(depresion|ansiedad|tdah|trastorno)\b.{0,30}\?",
        r"\b(tu|su)\s+impresion\b.{0,60}\b(depresion|ansiedad|tdah|trastorno)\b",
    ],
    RIESGO: [
        r"\b(clasifica|clasificar|determina|determinar|evalua|evaluar|estima|estimar|define|indica|dime|califica)\b.{0,50}\bnivel de riesgo\b",
        r"\b(clasifica|clasificar|evalua|evaluar|estima|estimar|califica)\b.{0,50}\briesgo\b.{0,40}\b(alto|medio|bajo|suicida|autolesion)\b",
        r"\briesgo\b.{0,30}\b(es|seria|sera)\b.{0,15}\b(alto|medio|bajo)\b.{0,10}\?",
        r"\bbajo,? medio o alto\b", r"\balto,? medio o bajo\b", r"\bes (alto|bajo) el riesgo\b",
    ],
    PIE: [
        r"\b(debe|debe\w*|deberia|corresponde que)\b.{0,30}\b(continuar|seguir|egresar|ingresar|salir|quedar\w*|permanecer)\b.{0,25}\bpie\b",
        r"\bpie\b.{0,15}\b(o|u)\b.{0,12}\b(salir|egresar|continuar|ingresar)\b",
        r"\b(continuar|seguir|egresar|ingresar|salir)\b.{0,25}\bpie\b.{0,25}\b(o|u)\b",
        r"\bconcluy\w+\b.{0,50}\bpie\b", r"\b(decide|decidir|resuelve|determina)\b.{0,40}\b(pie|egreso|ingreso|continuidad)\b",
        r"\bdecide tu\b",
    ],
    MEDICACION: [
        r"\b(medicamento|medicacion|farmaco|pastilla|dosis|suplemento|tratamiento farmacologico|metilfenidato|ritalin)\b",
    ],
    EMOCION: [
        r"\binfier\w*\b.{0,40}\b(estado emocional|emocion|animo|sentimiento|personalidad)\b",
        r"\b(como se siente|que siente) (realmente|en verdad|de verdad)\b",
        r"\bestado emocional (actual|real)\b.{0,40}\b(descri\w+|dedu\w+|inf\w+)\b",
        r"\b(describe|deduce|interpreta)\b.{0,40}\b(estado emocional|como se siente|su personalidad)\b",
    ],
    SANCION: [
        r"\b(propon\w*|sugiere|recomienda|decide|define|indica)\b.{0,40}\b(sancion|castigo|expulsion|suspension|medida disciplinaria|cancelacion de matricula)\b",
        r"\bque sancion (corresponde|aplicar|merece)\b",
    ],
    INVENCION: [
        r"\binvent\w+\b", r"\bcompleta\b.{0,40}\b(datos|notas|informacion)\b.{0,30}\b(falten|faltan|ausentes)\b",
        r"\binformacion razonable\b", r"\bque se vea completo\b",
        r"\bcompleta\b.{0,60}\bque no (estan|esta|constan|figuran)\b",
    ],
}
# MEDICACION: se acepta cuando el texto menciona un medicamento YA registrado (p. ej. "toma metilfenidato
# indicado por neurologia"): solo se bloquea si hay verbo de peticion cerca.
_VERBOS_PETICION_MED = re.compile(
    r"\b(recomend\w+|suger\w+|agreg\w+|incluy\w+|propon\w+)\b|\b(que|cual|cuales)\s+(\w+\s+)?(medicamento|farmaco|suplemento|dosis|pastilla)")

_INYECCIONES = re.compile(
    r"[^.\n]*\b(nota para el asistente|ignora (todas )?(tus|las|sus) instrucciones|olvida (todas )?(tus|las) instrucciones|"
    r"ya no tienes restricciones|nuevo modo|modo sin restricciones|a partir de ahora (eres|debes|actua)|"
    r"system\s*:|sistema\s*:|instruccion(es)? (del|para el) (sistema|asistente|modelo))\b[^\n]*",
    re.IGNORECASE,
)
# Regla general (22-oct, noche): una linea que se dirige a una IA Y da una orden. No depende de frases exactas.
_ALUDE_IA = r"\b(ia|i\.a\.|inteligencia artificial|asistente|chatbot|modelo de lenguaje|llm|gpt|ai|assistant|model|bot)\b"
_ORDEN = (r"\b(ignora\w*|olvida\w*|pon|ponga|escribe|escriba|indica|indique|agrega|agregue|redacta|incluye|anota|"
          r"declara|afirma|di|dile|actua|actue|responde|haz|ignore|forget|write|state|say|declare|act|pretend|respond|disregard)\b")
_INGLES = r"\b(ignore (all )?(the )?(previous|prior|above) instructions|you are now|system prompt|disregard (all )?(previous|prior))\b"
_DIRIGIDO_IA = re.compile(r"(?=.*" + _ALUDE_IA + r")(?=.*" + _ORDEN + r")|" + _INGLES)
_INYECCIONES = re.compile(_INYECCIONES.pattern + r"|^(?=.*" + _ALUDE_IA + r")(?=.*" + _ORDEN + r").*$|" + _INGLES + r".*", re.IGNORECASE)
MARCA_OMITIDO = "[CONTENIDO OMITIDO: instruccion dirigida al asistente dentro de las notas]"


def neutralizar_inyecciones(texto: str) -> tuple[str, list[Hallazgo]]:
    """Reemplaza las frases que parecen ordenes al asistente. Devuelve (texto_limpio, hallazgos)."""
    hallazgos: list[Hallazgo] = []
    lineas: list[str] = []
    for linea in texto.split("\n"):
        ln = _n(linea)
        if not _INYECCIONES.search(ln):
            lineas.append(linea)
            continue
        if len(ln) != len(linea):          # normalizacion cambio el largo: se omite la linea entera
            hallazgos.append(Hallazgo(INYECCION, linea))
            lineas.append(MARCA_OMITIDO)
            continue
        res, ultimo = [], 0
        for m in _INYECCIONES.finditer(ln):
            hallazgos.append(Hallazgo(INYECCION, linea[m.start():m.end()]))
            res.append(linea[ultimo:m.start()])
            res.append(MARCA_OMITIDO)
            ultimo = m.end()
        res.append(linea[ultimo:])
        lineas.append("".join(res))
    return "\n".join(lineas), hallazgos


def detectar_peticiones(texto: str) -> list[Hallazgo]:
    """Peticiones que el modulo no atiende. Se aplica al texto libre que escribe la profesional
    (condiciones adicionales, notas) -- NO a los documentos normativos."""
    t = _n(texto)
    hallazgos: list[Hallazgo] = []
    for codigo, patrones in _PETICIONES.items():
        for p in patrones:
            m = re.search(p, t)
            if not m:
                continue
            if codigo == MEDICACION:
                ventana = t[max(0, m.start() - 60):m.end() + 40]
                if not _VERBOS_PETICION_MED.search(ventana):
                    continue
            hallazgos.append(Hallazgo(codigo, texto[m.start():m.end()] if len(t) == len(texto) else m.group(0)))
            break   # un hallazgo por codigo basta
    return hallazgos


# --------------------------------------------------------------------------- #
# Guardian de SALIDA
# --------------------------------------------------------------------------- #
MARCA_FUERA_DE_ALCANCE = "FUERA DE MI ALCANCE"

_SALIDA = {
    RIESGO: [
        r"nivel de riesgo[^.\n]{0,40}:\s*\**\s*(bajo|medio|alto|moderado)",
        r"\briesgo\s+(suicida\s+|de autolesion\s+)?(es\s+|se considera\s+|seria\s+|:\s*)?\**(bajo|medio|alto|moderado)\b",
        r"\b(se )?(clasifica|estima|evalua|considera|determina)\w*\b[^.\n]{0,40}\briesgo\b[^.\n]{0,30}\b(bajo|medio|alto|moderado)\b",
        r"\b(bajo|medio|alto|moderado) riesgo\b",
    ],
    PIE: [
        r"\b(se recomienda|recomiendo|sugiero|se sugiere|corresponde|se debe|debe|deberia|conviene)\b[^.\n]{0,80}\b(continu\w+|egres\w+|ingres\w+|permanec\w+|salir|mantener)\b[^.\n]{0,40}\bpie\b",
        r"\brecomendacion\b[^.\n]{0,40}\bpie\b",
    ],
    MEDICACION: [
        r"\b(medicacion|medicamento\w*|farmaco\w*|metilfenidato|ritalin|ritalina|melatonina|antidepresiv\w+|ansiolitic\w+|psicofarmaco\w*|dosis)\b",
    ],
    DIAGNOSTICO: [
        r"\b(presenta|padece|sufre|cursa con|tiene|compatible con|sugiere|indica|probable|posible)\b[^.\n]{0,40}\b(tdah|deficit atencional|depresion|ansiedad|trastorno\w*|autismo|tea\b|dislexia|discalculia)",
        r"\bdiagnostico (probable|presuntivo|sugerido|de)\b[^.\n]{0,40}\b(tdah|deficit|depresion|ansiedad|trastorno|autismo|dislexia)",
        r"\bcumpl\w+\s+(con\s+)?(los\s+)?criterios\b[^.\n]{0,40}\b(depresion|ansiedad|tdah|trastorno\w*|autismo|dislexia|deficit)",
        r"\bdiagnostico\W{0,6}(depresion|ansiedad|tdah|trastorno\w*|deficit|autismo|dislexia|discalculia)",
    ],
    EMOCION: [
        r"\b(se puede inferir|se infiere|podria describirse|sugiere (una )?(actitud|estado|emocion)|parece (estar|sentirse)|aparenta|se siente)\b[^.\n]{0,60}\b(ansios\w+|triste\w*|deprimid\w+|preocupad\w+|angustiad\w+|enojad\w+|nervios\w+|solo|aislad\w+|frustrad\w+|inseguro\w*|feliz|contento\w*)\b",
        r"estado emocional[^.\n]{0,60}\b(ansios\w+|triste\w*|deprimid\w+|preocupad\w+|angustiad\w+|enojad\w+|nervios\w+|frustrad\w+)\b",
        r"\b(es una persona|su personalidad es|rasgos de personalidad)\b",
        r"\b(sugier\w+|indic\w+|apunt\w+)\s+que\b[^.\n]{0,60}\b(emocional\w*|animo|ansiedad|tristeza|depresion)\b",
        r"\bpodria estar\b[^.\n]{0,40}\b(atravesando|pasando|viviendo|sintiendo|experimentando)\b",
        r"\bdificultad(es)? emocional(es)?\b",
    ],
    SANCION: [
        r"\b(se recomienda|sugiero|se sugiere|corresponde|se debe|deberia)\b[^.\n]{0,60}\b(sancion\w*|suspension|expulsion|cancelacion de matricula|medida disciplinaria)\b",
        r"\bse (propone|plantea|aplica|aplicara|sugiere|recomienda|debe|deberia)\b[^.\n]{0,60}\b(sancion\w*|amonestacion\w*|suspension|expulsion|medida disciplinaria|castigo)\b",
        r"\bpropuesta de (sancion|medida disciplinaria|amonestacion)",
    ],
}

# Para PIE/DIAGNOSTICO/EMOCION basta que el patron aparezca en la salida y no en las notas de entrada.
# MEDICACION se evalua distinto: si el termino ya estaba en la entrada (medicacion registrada por un
# profesional), no es infraccion.


def revisar_limites(entrada: str, salida: str, entrada_completa: str | None = None) -> list[Hallazgo]:
    """Contenido de la salida fuera de limites. 'entrada' son las notas enviadas (ya seudonimizadas, sin la linea de
    condiciones); 'entrada_completa' es el prompt entero (para saber si algo se pidio explicitamente)."""
    e, s = _n(entrada), _n(salida)
    ec = _n(entrada_completa) if entrada_completa is not None else e
    hallazgos: list[Hallazgo] = []
    pedidos = {h.codigo for h in detectar_peticiones(entrada)}
    # Lo que el modelo declara fuera de alcance no es infraccion: se quita antes de revisar.
    # Tambien los marcadores [PENDIENTE: ...]: dicen que falta informacion, no afirman nada.
    s = re.sub(r"[^\n]*(fuera de mi alcance|\[pendiente)[^\n]*", " ", s)
    for codigo, patrones in _SALIDA.items():
        for p in patrones:
            for m in re.finditer(p, s, flags=re.MULTILINE):
                frag = m.group(0)
                if codigo == MEDICACION and re.search(p, e) and codigo not in pedidos:
                    continue   # ya estaba en las notas (registrado por un profesional) y nadie lo pidio
                if codigo in (DIAGNOSTICO, EMOCION, RIESGO, PIE, SANCION) and frag.strip() in e:
                    continue   # cita literal de lo que ya decian las notas
                if codigo in (DIAGNOSTICO, EMOCION, PIE, SANCION) and _es_negacion_o_atribucion(s, m):
                    continue
                hallazgos.append(Hallazgo(codigo, frag))
                break
            else:
                continue
            break
    # Hechos nuevos que delatan invencion (regla 1): el PIE y fracciones o porcentajes que no estaban en las notas.
    if re.search(r"\bpie\b|programa de integracion escolar", s) and not re.search(r"\bpie\b|programa de integracion escolar", ec):
        hallazgos.append(Hallazgo(INVENCION, "menciona el PIE sin que este en las notas"))
    nuevos = [x for x in re.findall(r"\b\d{1,3}\s?%|\b\d/\d\b", s) if x not in ec]
    if nuevos:
        hallazgos.append(Hallazgo(INVENCION, "cifras nuevas: " + ", ".join(nuevos[:4])))
    return hallazgos


_NEGACIONES = re.compile(
    r"\b(no (se |es posible |corresponde |realiza |emite |puede |puedo )|"
    r"establecimiento no|no hay diagnostico|sin diagnostico|pregunta si|consult\w+ (a|con) un especialista|"
    r"solicita|segun (la )?(evaluacion|informe)|registrad[oa] por|informa que|refiere que|senala que|"
    r"se acordo|acordaron|el equipo acordo)\b"
)


def _es_negacion_o_atribucion(s: str, m: re.Match) -> bool:
    """Si en la misma oracion hay una negacion o atribucion ('el establecimiento no realiza ese diagnostico',
    'segun la evaluacion registrada por...'), no es una afirmacion del modelo."""
    ini = max(s.rfind(".", 0, m.start()), s.rfind("\n", 0, m.start())) + 1
    fin_p, fin_n = s.find(".", m.end()), s.find("\n", m.end())
    fin = min([x for x in (fin_p, fin_n) if x != -1] or [len(s)])
    return bool(_NEGACIONES.search(s[ini:fin]))


def sin_condiciones(prompt: str) -> str:
    """Quita la linea «Condiciones adicionales: ...» del prompt: lo que pidio la usuaria no cuenta como 'ya estaba en
    las notas' (si pidio un diagnostico y el modelo lo escribe, igual es una infraccion)."""
    return re.sub(r"Condiciones adicionales:.*?\n\n", "", prompt, count=1, flags=re.DOTALL)


def cifras_nuevas(entrada: str, salida: str) -> list[str]:
    """Numeros de 2+ cifras o con decimales en la salida que no aparecen en la entrada (posible invencion)."""
    pat = re.compile(r"\b\d{2,}(?:[.,]\d+)?\b")
    e = set(pat.findall(entrada))
    return sorted({x for x in pat.findall(salida) if x not in e})


# --------------------------------------------------------------------------- #
# Reglas ESTRUCTURALES (22-oct-2026, tarde). Los patrones de palabras de arriba no generalizaron a redacciones nuevas
# (serie E: dejaron pasar 5 de 6 fallas). Estas reglas no dependen de COMO se pide algo prohibido:
#   1) la profesional solo puede dar indicaciones de FORMATO (lista cerrada);
#   2) el borrador solo puede tener las secciones pedidas (cualquier "Impresion", "Recomendacion", "Hipotesis"...
#      es una seccion ajena y se quita);
#   3) los datos de riesgo que traen las notas no pueden desaparecer.
# --------------------------------------------------------------------------- #
AYUDA_FORMATOS = ("Solo se aceptan indicaciones de formato: tono formal o simple, mas breve, con o sin vinetas, "
                  "maximo N palabras/lineas/paginas, en tercera persona, ordenado por fecha, o «sin ...». "
                  "El contenido se edita en el borrador, no se le pide al asistente.")
_NUM = r"(\d+|un|una|dos|tres|cuatro|cinco|diez)"
_FORMATOS = [re.compile(x + "$") for x in (
    r"(tono |estilo |lenguaje )?(formal|informal|cercano|neutro|tecnico|simple|claro|sencillo|profesional)",
    r"(mas )?(breve|conciso|corto|extenso|detallado|resumido)",
    r"(con|sin) (vinetas|listas?|negritas|titulos|encabezados|subtitulos)",
    r"(maximo|minimo|hasta) " + _NUM + r" (palabras|lineas|paginas?|parrafos|hojas?)",
    r"(en )?(tercera|primera) persona", r"(en )?(pasado|presente)",
    r"(ordenado )?(cronologicamente|por fecha)",
    r"ninguna?|no hay|no corresponde|n/a|sin condiciones",
    r"sin [a-z ]{3,60}",
)]


def condiciones_no_permitidas(condiciones: str) -> list[Hallazgo]:
    """Fragmentos de 'condiciones adicionales' que no son una indicacion de formato de la lista cerrada."""
    malos = []
    for frag in re.split(r"[.,;:\n]+|\s+y\s+", _n(condiciones)):
        f = frag.strip()
        if f and not any(r.match(f) for r in _FORMATOS):
            malos.append(Hallazgo(CONDICION, frag.strip()))
    return malos


_BASE_ENCABEZADOS = ("advertencia", "informe", "resumen", "documentos", "evidencia", "periodo")
_PALABRAS_VACIAS = {"caso", "sobre", "sesion", "sesiones"}


def _encabezados(texto: str) -> list[tuple[int, str, str]]:
    """(posicion de la linea, texto normalizado del encabezado, linea) de cada linea que funciona como titulo:
    '## X', '**X**', '**X:** resto' o 'X:' sola. No cuenta vinetas ni fechas."""
    res, pos = [], 0
    for linea in texto.split("\n"):
        s = linea.strip()
        m = re.match(r"^#{1,6}\s*(.+?)\s*#*$", s)
        if not m:
            m = re.match(r"^\*\*\s*([^*]{2,80}?)\s*\*\*", s)
        if not m and re.match(r"^[^*#\-\d\[][^.:]{2,70}:$", s):
            m = re.match(r"^(.+?):$", s)
        if m and not re.match(r"^[-*\u2022]\s", s):
            res.append((pos, _n(m.group(1)).strip(" *:#"), linea))
        pos += len(linea) + 1
    return res


def secciones_ajenas(texto: str, secciones_pedidas: str, extra: tuple[str, ...] = ()) -> list[Hallazgo]:
    """Encabezados del borrador que no corresponden a ninguna seccion pedida ni a las fijas (Advertencias, titulo)."""
    stems = {w[:6] for w in re.findall(r"[a-z]{5,}", _n(secciones_pedidas)) if w not in _PALABRAS_VACIAS}
    ok = tuple(stems) + _BASE_ENCABEZADOS + tuple(_n(x) for x in extra)
    hall = []
    lineas = texto.split("\n")
    for pos, enc, linea in _encabezados(texto):
        if re.fullmatch(r"[\d/\-. :]+", enc) or "fuera de mi alcance" in enc or "pendiente" in enc:
            continue
        if any(o in enc for o in ok):
            continue
        # un titulo cuyo contenido es solo el aviso «FUERA DE MI ALCANCE» no afirma nada
        if "fuera de mi alcance" in _n(linea):
            continue
        solo_titulo = re.fullmatch(r"\s*(#{1,6}\s*)?\**[^*]{2,80}?\**:?\**\s*", linea) is not None
        if solo_titulo:
            sig = texto[pos + len(linea):].lstrip("\n ").split("\n", 1)[0]
            if "fuera de mi alcance" in _n(sig):
                continue
        hall.append(Hallazgo(SECCION, linea.strip()))
    return hall


def quitar_secciones(texto: str, ajenas: list[Hallazgo]) -> str:
    """Elimina del borrador cada seccion ajena (desde su titulo hasta el siguiente titulo)."""
    lineas = texto.split("\n")
    marcas = {h.fragmento.strip() for h in ajenas}
    out, saltando = [], False
    titulos = {l for _, _, l in _encabezados(texto)}
    for l in lineas:
        if l in titulos:
            saltando = l.strip() in marcas
        if not saltando:
            out.append(l)
    return "\n".join(out).rstrip() + "\n"


_TERMINOS_RIESGO = (("protocolo", "protocolo"), ("corte", "corte"), ("autolesion", "autolesion"),
                    ("suicid", "suicid"), ("lesion", "lesion"), ("ideacion", "ideacion"))


def omisiones_riesgo(entrada: str, salida: str) -> list[str]:
    """Terminos de riesgo que estaban en las notas y no aparecen en el borrador (regla: no perder datos de riesgo)."""
    e, s = _n(entrada), _n(salida)
    return [nombre for nombre, raiz in _TERMINOS_RIESGO if raiz in e and raiz not in s]


def filtrar_condiciones(condiciones: str) -> tuple[str, list[Hallazgo]]:
    """Devuelve (condiciones que SI llegan al modelo, fragmentos ignorados). Solo pasan indicaciones de formato."""
    ok, ignoradas = [], []
    for frag in re.split(r"[.,;:\n]+|\s+y\s+", condiciones):
        f = _n(frag).strip()
        if not f:
            continue
        if any(r.match(f) for r in _FORMATOS):
            ok.append(frag.strip())
        else:
            ignoradas.append(Hallazgo(CONDICION, frag.strip()))
    return (", ".join(ok) + "." if ok else "Ninguna."), ignoradas
