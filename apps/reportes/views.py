from django.shortcuts import render

from apps.auditoria.servicios import registrar
from apps.core.filtros import Filtros
from apps.cuentas.permisos import permiso_requerido

from .servicios import resumen


@permiso_requerido("reportes.ver")
def panel(request):
    """«Atención psicosocial › Estadísticas»: cifras agregadas del periodo, sin datos personales (RF-15)."""
    f = Filtros(request, usar=("anio", "mes"))
    registrar(request.user, "consulta", "reportes", None)
    return render(request, "reportes/panel.html", {**f.contexto(), "r": resumen(f.desde, f.hasta)})
