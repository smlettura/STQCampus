"""Descargas en Excel (openpyxl) y PDF (reportlab) usadas por las pantallas del prototipo v1.

- Excel: una o varias hojas con encabezado destacado, filtros y anchos de columna. Los textos que empiezan con «=», «+»,
  «-» o «@» se guardan como texto para que Excel no los interprete como fórmulas (inyección de fórmulas).
- PDF: fichas y nóminas en tamaño carta con el nombre del colegio, fecha de emisión y leyenda de confidencialidad.
"""
import datetime
import io

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone

MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _descarga(contenido, nombre, tipo):
    respuesta = HttpResponse(contenido, content_type=tipo)
    respuesta["Content-Disposition"] = 'attachment; filename="%s"' % nombre.replace('"', "")
    return respuesta


# ---------------------------------------------------------------------------------------------------------- Excel
def libro_excel(hojas):
    """hojas: lista de (título, encabezados, filas). Devuelve los bytes del .xlsx."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    libro = Workbook()
    libro.remove(libro.active)
    for titulo, encabezados, filas in hojas:
        hoja = libro.create_sheet(title=_titulo_hoja(titulo))
        hoja.append(list(encabezados))
        for celda in hoja[1]:
            celda.font = Font(bold=True, color="FFFFFF")
            celda.fill = PatternFill("solid", fgColor="0A1120")
            celda.alignment = Alignment(vertical="center")
        anchos = [len(str(e)) for e in encabezados]
        for fila in filas:
            hoja.append([_valor(v) for v in fila])
            for celda in hoja[hoja.max_row]:
                if isinstance(celda.value, str):
                    celda.data_type = "s"          # nunca una fórmula
            for i, v in enumerate(fila):
                anchos[i] = max(anchos[i], min(len(str(v if v is not None else "")), 60))
        for i, ancho in enumerate(anchos, start=1):
            hoja.column_dimensions[get_column_letter(i)].width = max(10, ancho + 2)
        hoja.freeze_panes = "A2"
        if hoja.max_row > 1:
            hoja.auto_filter.ref = hoja.dimensions
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def _titulo_hoja(titulo):
    for c in '[]:*?/\\':
        titulo = titulo.replace(c, " ")
    return titulo[:31] or "Hoja"


def _valor(v):
    if isinstance(v, datetime.datetime):
        return timezone.localtime(v).replace(tzinfo=None) if timezone.is_aware(v) else v
    if isinstance(v, bool):
        return "Sí" if v else "No"
    return v


def respuesta_excel(nombre, hojas):
    return _descarga(libro_excel(hojas), nombre, MIME_XLSX)


def leer_excel(archivo):
    """Devuelve (encabezados normalizados, filas como diccionarios con su número de fila) de la primera hoja."""
    from openpyxl import load_workbook

    libro = load_workbook(archivo, read_only=True, data_only=True)
    hoja = libro.worksheets[0]
    filas = hoja.iter_rows(values_only=True)
    try:
        encabezados = [normalizar_encabezado(c) for c in next(filas)]
    except StopIteration:
        return [], []
    datos = []
    for numero, fila in enumerate(filas, start=2):
        if fila is None or all(v in (None, "") for v in fila):
            continue
        datos.append((numero, {encabezados[i]: v for i, v in enumerate(fila) if i < len(encabezados) and encabezados[i]}))
    libro.close()
    return encabezados, datos


def normalizar_encabezado(texto):
    import unicodedata
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().lower().strip()
    return "_".join(texto.replace("*", "").split())


# ---------------------------------------------------------------------------------------------------------- PDF
class DocumentoPDF:
    """Constructor simple de PDF (tamaño carta) sobre reportlab.platypus."""

    def __init__(self, titulo, subtitulo=""):
        from reportlab.lib import colors
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

        self.titulo, self.subtitulo = titulo, subtitulo
        self.colors = colors
        base = getSampleStyleSheet()
        self.estilos = {
            "titulo": ParagraphStyle("t", parent=base["Title"], fontName="Helvetica-Bold", fontSize=17, leading=21,
                                     alignment=0, spaceAfter=2, textColor=colors.HexColor("#0B1220")),
            "sub": ParagraphStyle("s", parent=base["Normal"], fontName="Helvetica", fontSize=9.5, leading=13,
                                  textColor=colors.HexColor("#4B5563"), spaceAfter=10),
            "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, leading=15,
                                 spaceBefore=12, spaceAfter=6, textColor=colors.HexColor("#0B1220")),
            "p": ParagraphStyle("p", parent=base["Normal"], fontName="Helvetica", fontSize=9.5, leading=13),
            "celda": ParagraphStyle("c", parent=base["Normal"], fontName="Helvetica", fontSize=8.8, leading=11),
            "celda_b": ParagraphStyle("cb", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8.8, leading=11),
        }
        self.historia = []
        self._encabezado_pagina()

    def _p(self, texto, estilo="p"):
        from reportlab.platypus import Paragraph
        from xml.sax.saxutils import escape
        return Paragraph(escape(str(texto if texto not in (None, "") else "—")).replace("\n", "<br/>"),
                         self.estilos[estilo])

    def _encabezado_pagina(self):
        from reportlab.platypus import Paragraph
        self.historia.append(Paragraph(self.titulo, self.estilos["titulo"]))
        if self.subtitulo:
            self.historia.append(self._p(self.subtitulo, "sub"))

    def seccion(self, texto):
        self.historia.append(self._p(texto, "h2"))

    def parrafo(self, texto):
        self.historia.append(self._p(texto))

    def datos(self, pares, columnas=2):
        """Pares (rótulo, valor) en una grilla de `columnas` columnas."""
        from reportlab.platypus import Table, TableStyle
        filas, fila = [], []
        for rotulo, valor in pares:
            fila += [self._p(rotulo, "celda"), self._p(valor, "celda_b")]
            if len(fila) == columnas * 2:
                filas.append(fila)
                fila = []
        if fila:
            filas.append(fila + [""] * (columnas * 2 - len(fila)))
        ancho = 540 / columnas
        tabla = Table(filas, colWidths=[ancho * .42, ancho * .58] * columnas)
        tabla.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                                   ("TEXTCOLOR", (0, 0), (-1, -1), self.colors.HexColor("#1F2937")),
                                   ("LINEBELOW", (0, 0), (-1, -1), .4, self.colors.HexColor("#DDE2E9"))]))
        self.historia.append(tabla)

    def tabla(self, encabezados, filas, anchos=None, vacio="Sin registros."):
        from reportlab.platypus import Table, TableStyle
        if not filas:
            self.parrafo(vacio)
            return
        datos = [[self._p(e, "celda_b") for e in encabezados]] + [[self._p(v, "celda") for v in f] for f in filas]
        tabla = Table(datos, colWidths=anchos, repeatRows=1)
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), self.colors.HexColor("#EEF1F5")),
            ("LINEBELOW", (0, 0), (-1, 0), .8, self.colors.HexColor("#CBD2DC")),
            ("LINEBELOW", (0, 1), (-1, -1), .4, self.colors.HexColor("#DDE2E9")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        self.historia.append(tabla)

    def nueva_pagina(self, titulo, subtitulo=""):
        from reportlab.platypus import PageBreak
        self.historia.append(PageBreak())
        self.titulo, self.subtitulo = titulo, subtitulo
        self._encabezado_pagina()

    def generar(self):
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate

        buffer = io.BytesIO()
        emitido = timezone.localtime().strftime("%d/%m/%Y %H:%M")

        def pie(canvas, doc):
            canvas.saveState()
            canvas.setFont("Helvetica", 7.5)
            canvas.setFillColor(self.colors.HexColor("#4B5563"))
            canvas.drawString(36, 24, "%s · %s · emitido el %s" % (settings.NOMBRE_COLEGIO, settings.NOMBRE_MARCA, emitido))
            canvas.drawRightString(letter[0] - 36, 24, "Documento confidencial (Ley 21.719) · página %d" % doc.page)
            canvas.restoreState()

        doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=44,
                                title=self.titulo, author=settings.NOMBRE_COLEGIO)
        doc.build(self.historia, onFirstPage=pie, onLaterPages=pie)
        return buffer.getvalue()

    def respuesta(self, nombre):
        return _descarga(self.generar(), nombre, "application/pdf")
