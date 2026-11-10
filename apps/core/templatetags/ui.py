from django import template
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe

from apps.core.validadores import formatear_rut

register = template.Library()

COLORES = {
    # casos
    "abierto": "verde", "seguimiento": "", "cerrado": "gris",
    # evaluación, planes, informes
    "en_proceso": "ambar", "cerrada": "gris", "vigente": "verde", "borrador": "ambar", "validado": "verde",
    "entregado": "gris",
    # IA
    "generado": "morado", "descartado": "gris",
    # alertas
    "registrada": "rojo", "en_gestion": "ambar", "denunciada": "morado",
    # cumplimiento
    "recibida": "ambar", "en_analisis": "ambar", "respondida": "verde", "rechazada": "gris",
    "propuesta": "ambar", "autorizada": "rojo", "postergada": "gris", "ejecutada": "gris",
    "pendiente": "ambar", "enviado": "ambar", "atendido": "verde",
    # convivencia y plan de gestión
    "realizada": "verde", "en_proceso_conflicto": "ambar", "con_acuerdo": "verde", "sin_acuerdo": "gris",
    "positiva": "verde", "moderada": "ambar", "grave": "naranjo", "gravisima": "rojo",
    # estudiantes
    "activo": "verde", "inactivo": "gris", "egresado": "",
    "promovido": "verde", "repite": "ambar", "egresa": "",
}

# Íconos de trazo (24×24), los mismos del diseño «panel analítico». Se dibujan con currentColor.
ICONOS = {
    "inicio": ["M3 10.5 12 3l9 7.5", "M5 9.5V21h5v-6h4v6h5V9.5"],
    "estudiantes": ["M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2", "M5 7a4 4 0 1 0 8 0a4 4 0 1 0-8 0",
                    "M22 21v-2a4 4 0 0 0-3-3.87", "M16 3.13a4 4 0 0 1 0 7.75"],
    "atencion": ["M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21.2l8.8-8.8a5.5 5.5 0 0 0 0-7.8z"],
    "alertas": ["M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z", "M12 9v4", "M12 17h.01"],
    "convivencia": ["M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"],
    "protocolos": ["M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z", "M14 2v6h6"],
    "plan": ["M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z", "M16 2v4", "M8 2v4", "M3 10h18"],
    "indicadores": ["M3 3v18h18", "M8 17v-4", "M12 17V9", "M16 17v-6"],
    "gestion": ["M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2",
                "M9 3h6v4H9z", "m9 14 2 2 4-4"],
    "admin": ["M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z", "m9 12 2 2 4-4"],
    "buscar": ["M4 11a7 7 0 1 0 14 0a7 7 0 1 0-14 0", "m21 21-4.3-4.3"],
    "campana": ["M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9", "M10.3 21a1.94 1.94 0 0 0 3.4 0"],
    "salir": ["M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4", "m16 17 5-5-5-5", "M21 12H9"],
    "menu": ["M4 6h16", "M4 12h16", "M4 18h16"],
    "mas": ["M12 5v14", "M5 12h14"],
    "flecha": ["m9 18 6-6-6-6"],
    "ojo": ["M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z", "M9 12a3 3 0 1 0 6 0a3 3 0 1 0-6 0"],
    "descargar": ["M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4", "m7 10 5 5 5-5", "M12 15V3"],
    "subir": ["M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4", "m17 8-5-5-5 5", "M12 3v12"],
    "carpeta": ["M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"],
    "puntos": ["M5 12h.01", "M12 12h.01", "M19 12h.01"],
    "info": ["M2 12a10 10 0 1 0 20 0a10 10 0 1 0-20 0", "M12 16v-4", "M12 8h.01"],
    "chispa": ["M12 3v4", "M12 17v4", "M3 12h4", "M17 12h4", "m6 6 2.5 2.5", "m15.5 15.5 2.5 2.5",
               "m18 6-2.5 2.5", "m8.5 15.5-2.5 2.5"],
    "chevron": ["m6 9 6 6 6-6"],
    "editar": ["M12 20h9", "M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"],
    "candado": ["M6 11h12a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2z", "M8 11V7a4 4 0 0 1 8 0v4"],
}


@register.filter
def rut(valor):
    return formatear_rut(valor)


@register.filter
def color_estado(valor):
    return COLORES.get(valor, "")


@register.simple_tag(takes_context=True)
def activo(context, prefijo):
    request = context.get("request")
    return "activo" if request is not None and request.path.startswith(prefijo) else ""


@register.simple_tag
def icono(nombre, tamano=18):
    trazos = format_html_join("", '<path d="{}"/>', ((d,) for d in ICONOS.get(nombre, [])))
    return mark_safe('<svg class="icono" width="%d" height="%d" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                     'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" '
                     'focusable="false">%s</svg>' % (int(tamano), int(tamano), trazos))


@register.filter
def miles(valor):
    """1487 -> «1.487» (separador de miles chileno)."""
    try:
        return "{:,}".format(int(valor)).replace(",", ".")
    except (TypeError, ValueError):
        return valor


@register.filter
def pct(valor, decimales=1):
    """97.8 -> «97,8%». Recibe un porcentaje (0 a 100); None -> «—»."""
    if valor is None:
        return "—"
    try:
        return ("%.*f%%" % (int(decimales), float(valor))).replace(".", ",")
    except (TypeError, ValueError):
        return valor


@register.filter
def clave(diccionario, llave):
    try:
        return diccionario.get(llave)
    except AttributeError:
        return None


@register.simple_tag(takes_context=True)
def url_con(context, **cambios):
    """Conserva los parámetros GET actuales y cambia o quita los indicados (valor vacío = quitar)."""
    from django.utils.http import urlencode
    request = context.get("request")
    params = dict(request.GET.items()) if request is not None else {}
    for k, v in cambios.items():
        if v in (None, ""):
            params.pop(k, None)
        else:
            params[k] = v
    params.pop("pagina", None) if "pagina" not in cambios else None
    return "?" + urlencode(params)


# ---------------------------------------------------------------------------------------------- texto de informes
_NEGRITA = __import__("re").compile(r"\*\*(.+?)\*\*")
_MARCA = __import__("re").compile(r"\[(FUERA DE MI ALCANCE|VERIFICAR|CONTENIDO OMITIDO)([^\]]*)\]")


def _en_linea(texto):
    from django.utils.html import escape
    t = escape(texto)
    t = _NEGRITA.sub(r"<strong>\1</strong>", t)
    return _MARCA.sub(r'<span class="marca-revisar">[\1\2]</span>', t)


@register.filter
def formato_informe(texto):
    """Presenta el texto de un informe (formato simple tipo Markdown que usan las profesionales y el copiloto):
    «#/##/###» títulos, «* » o «- » viñetas, «1. » listas numeradas y **negrita**. Todo se escapa antes de dar formato,
    así que no se puede inyectar HTML. Omite un título inicial «Informe…», porque el documento ya lo muestra."""
    import re
    lineas = (texto or "").replace("\r\n", "\n").split("\n")
    while lineas and not lineas[0].strip():
        lineas.pop(0)
    if lineas and re.match(r"^#{1,3}\s+informe\b", lineas[0].strip(), re.I):
        lineas.pop(0)
    html, parrafo, lista = [], [], None

    def cerrar_parrafo():
        if parrafo:
            html.append("<p>%s</p>" % "<br>".join(parrafo))
            parrafo.clear()

    def cerrar_lista():
        nonlocal lista
        if lista:
            html.append("</%s>" % lista)
            lista = None

    for cruda in lineas:
        linea = cruda.strip()
        titulo = re.match(r"^(#{1,6})\s+(.*)$", linea)
        vineta = re.match(r"^[*\-•]\s+(.*)$", linea)
        numero = re.match(r"^\d+[.)]\s+(.*)$", linea)
        if not linea:
            cerrar_parrafo()
            cerrar_lista()
        elif titulo:
            cerrar_parrafo()
            cerrar_lista()
            nivel = "h3" if len(titulo.group(1)) <= 3 else "h4"
            html.append("<%s>%s</%s>" % (nivel, _en_linea(titulo.group(2).strip("# ")), nivel))
        elif vineta or numero:
            cerrar_parrafo()
            tipo = "ul" if vineta else "ol"
            if lista != tipo:
                cerrar_lista()
                html.append("<%s>" % tipo)
                lista = tipo
            html.append("<li>%s</li>" % _en_linea((vineta or numero).group(1)))
        else:
            cerrar_lista()
            parrafo.append(_en_linea(linea))
    cerrar_parrafo()
    cerrar_lista()
    return mark_safe("\n".join(html))
