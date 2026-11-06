"""Pantalla «Generar informe (IA)» del prototipo v1. El módulo de IA está en configuración: la pantalla muestra los datos
reales que usará (estudiante, periodo y atenciones), pero la generación queda deshabilitada."""
import datetime

from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.auditoria.servicios import registrar
from apps.casos.acceso import casos_visibles
from apps.casos.models import SesionSeguimiento
from apps.cuentas.permisos import permiso_requerido
from apps.estudiantes.acceso import estudiantes_visibles

from . import servicios


@require_GET
@permiso_requerido("ia.usar")
def generar_informe(request):
    u = request.user
    casos = casos_visibles(u)
    estudiantes = (estudiantes_visibles(u).filter(casos__in=casos).distinct()
                   .select_related("curso").order_by("apellido_paterno", "apellido_materno", "primer_nombre"))
    periodo = request.GET.get("periodo", "3")
    periodo = int(periodo) if periodo in {str(p) for p, _ in servicios.PERIODOS} else 3
    estudiante, sesiones, caso_abierto = None, [], None
    if request.GET.get("estudiante", "").isdigit():
        estudiante = estudiantes.filter(pk=int(request.GET["estudiante"])).first()
    if estudiante is not None:
        desde = timezone.now() - datetime.timedelta(days=30 * periodo)
        sesiones = (SesionSeguimiento.objects.filter(caso__in=casos.filter(estudiante=estudiante), estado="registrada",
                                                     fecha_hora__gte=desde)
                    .filter(Q(nivel_acceso="equipo") | Q(profesional=u)).order_by("-fecha_hora"))
        caso_abierto = casos.filter(estudiante=estudiante).exclude(estado="cerrado").first()
        registrar(u, "consulta", "estudiante", estudiante.pk, detalle="generar informe (IA): listado de atenciones")
    return render(request, "ia/generar_informe.html", {
        "estudiantes": estudiantes, "estudiante": estudiante, "periodo": periodo, "periodos": servicios.PERIODOS,
        "sesiones": sesiones, "caso_abierto": caso_abierto, "tipos": servicios.TIPOS_INFORME,
        "secciones": servicios.SECCIONES, "secciones_defecto": servicios.SECCIONES_POR_DEFECTO,
        "disponible": servicios.DISPONIBLE, "hoy": timezone.localdate()})
