"""Filtros globales de la barra superior (Año, Mes, Curso, Nivel, Programa), como en el prototipo v1.

Cada pantalla declara qué filtros usa. Los filtros viajan como parámetros GET (`anio`, `mes`, `curso`, `nivel`,
`programa`), de modo que los enlaces se pueden compartir y funcionan sin JavaScript.
"""
import calendar
import datetime

from django.utils import timezone
from django.utils.http import urlencode

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
NIVELES = [("prebasica", "Prebásica"), ("basica", "Básica"), ("media", "Media")]
PROGRAMAS = [("pie", "PIE"), ("prioritario", "Prioritario"), ("ninguno", "Sin programa")]


def _entero(valor, minimo, maximo):
    try:
        n = int(valor)
    except (TypeError, ValueError):
        return None
    return n if minimo <= n <= maximo else None


class Filtros:
    def __init__(self, request, usar=("anio", "mes", "curso"), etiqueta_anio="Año", niveles=NIVELES):
        from apps.estudiantes.models import Curso

        self.request = request
        self.usar = tuple(usar)
        self.etiqueta_anio = etiqueta_anio
        self.niveles = niveles
        self.hoy = timezone.localdate()
        g = request.GET
        self.anio = _entero(g.get("anio"), 2000, self.hoy.year + 1) or self.hoy.year
        self.mes = _entero(g.get("mes"), 1, 12) if "mes" in self.usar else None
        self.nivel = g.get("nivel") if "nivel" in self.usar and g.get("nivel") in dict(niveles) else None
        self.programa = g.get("programa") if "programa" in self.usar and g.get("programa") in dict(PROGRAMAS) else None
        self.cursos = list(Curso.objects.filter(anio_escolar=self.anio).ordenados()) if "curso" in self.usar else []
        curso = _entero(g.get("curso"), 1, 10 ** 12) if "curso" in self.usar else None
        self.curso = next((c for c in self.cursos if c.pk == curso), None)

    # ------------------------------------------------------------------ rangos de fechas
    @property
    def desde(self):
        return datetime.date(self.anio, self.mes or 1, 1)

    @property
    def hasta(self):
        mes = self.mes or 12
        return datetime.date(self.anio, mes, calendar.monthrange(self.anio, mes)[1])

    @property
    def nombre_mes(self):
        return MESES[self.mes - 1] if self.mes else ""

    def filtrar_fecha(self, qs, campo):
        return qs.filter(**{"%s__gte" % campo: self.desde, "%s__lte" % campo: self.hasta})

    def filtrar_fecha_hora(self, qs, campo):
        from apps.core.validadores import inicio_del_dia
        return qs.filter(**{"%s__gte" % campo: inicio_del_dia(self.desde),
                            "%s__lt" % campo: inicio_del_dia(self.hasta + datetime.timedelta(days=1))})

    # ------------------------------------------------------------------ enlaces de los menús
    def valores(self):
        v = {"anio": self.anio}
        if self.mes:
            v["mes"] = self.mes
        if self.curso:
            v["curso"] = self.curso.pk
        if self.nivel:
            v["nivel"] = self.nivel
        if self.programa:
            v["programa"] = self.programa
        return v

    def url(self, **cambios):
        v = self.valores()
        for clave, valor in cambios.items():
            if valor in (None, ""):
                v.pop(clave, None)
            else:
                v[clave] = valor
        if "anio" in cambios and "curso" not in cambios:
            v.pop("curso", None)          # los cursos cambian de un año a otro
        # Se conservan los demás parámetros de la página (pestañas, búsqueda), salvo la paginación.
        extra = {k: val for k, val in self.request.GET.items()
                 if k not in ("anio", "mes", "curso", "nivel", "programa", "pagina")}
        return "?" + urlencode({**extra, **v})

    def anios(self):
        from apps.estudiantes.models import Curso
        anios = set(Curso.objects.values_list("anio_escolar", flat=True).distinct()) | {self.hoy.year, self.anio}
        return sorted((a for a in anios if a >= self.hoy.year - 6), reverse=True)

    def menus(self):
        menus = []
        if "anio" in self.usar:
            menus.append({"etiqueta": "%s: %s" % (self.etiqueta_anio, self.anio), "opciones": [
                {"texto": str(a), "url": self.url(anio=a), "activo": a == self.anio} for a in self.anios()]})
        if "mes" in self.usar:
            menus.append({"etiqueta": "Mes: %s" % (self.nombre_mes.capitalize() or "Todos"), "opciones": [
                {"texto": "Todos", "url": self.url(mes=None), "activo": not self.mes}] + [
                {"texto": m.capitalize(), "url": self.url(mes=i + 1), "activo": self.mes == i + 1}
                for i, m in enumerate(MESES)]})
        if "programa" in self.usar:
            menus.append({"etiqueta": "Programa: %s" % (dict(PROGRAMAS).get(self.programa) or "Todos"), "opciones": [
                {"texto": "Todos", "url": self.url(programa=None), "activo": not self.programa}] + [
                {"texto": t, "url": self.url(programa=c), "activo": self.programa == c} for c, t in PROGRAMAS]})
        if "nivel" in self.usar:
            menus.append({"etiqueta": "Nivel: %s" % (dict(self.niveles).get(self.nivel) or "Todos"), "opciones": [
                {"texto": "Todos", "url": self.url(nivel=None), "activo": not self.nivel}] + [
                {"texto": t, "url": self.url(nivel=c), "activo": self.nivel == c} for c, t in self.niveles]})
        if "curso" in self.usar:
            menus.append({"etiqueta": "Curso: %s" % (self.curso.nombre if self.curso else "Todos"), "opciones": [
                {"texto": "Todos", "url": self.url(curso=None), "activo": not self.curso}] + [
                {"texto": c.nombre, "url": self.url(curso=c.pk), "activo": self.curso == c} for c in self.cursos]})
        return menus

    def contexto(self):
        return {"filtros": self, "filtros_barra": self.menus()}
