"""Pantallas del copiloto: «Generar informe (IA)», estado de la solicitud y revisión del borrador (RF-16 a RF-19)."""
import datetime

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.servicios import registrar
from apps.casos.acceso import casos_visibles
from apps.casos.models import SesionSeguimiento
from apps.cuentas.permisos import denegar, permiso_requerido
from apps.estudiantes.acceso import estudiantes_visibles

from . import servicios
from .models import ContenidoIA, RetroalimentacionIA, SolicitudIA


def _sesiones_disponibles(usuario, casos, estudiante, periodo):
    desde = timezone.now() - datetime.timedelta(days=30 * periodo)
    return (SesionSeguimiento.objects.filter(caso__in=casos.filter(estudiante=estudiante), estado="registrada",
                                             fecha_hora__gte=desde)
            .filter(Q(nivel_acceso="equipo") | Q(profesional=usuario)).select_related("caso", "profesional")
            .order_by("-fecha_hora"))


def _periodo(valor):
    return int(valor) if valor in {str(p) for p, _ in servicios.PERIODOS} else 3


@require_GET
@permiso_requerido("ia.usar")
def generar_informe(request):
    u = request.user
    casos = casos_visibles(u)
    estudiantes = (estudiantes_visibles(u).filter(casos__in=casos).distinct()
                   .select_related("curso").order_by("apellido_paterno", "apellido_materno", "primer_nombre"))
    periodo = _periodo(request.GET.get("periodo", "3"))
    estudiante, sesiones, caso_abierto = None, [], None
    if request.GET.get("estudiante", "").isdigit():
        estudiante = estudiantes.filter(pk=int(request.GET["estudiante"])).first()
    if estudiante is not None:
        sesiones = _sesiones_disponibles(u, casos, estudiante, periodo)
        caso_abierto = casos.filter(estudiante=estudiante).exclude(estado="cerrado").first()
        registrar(u, "consulta", "estudiante", estudiante.pk, detalle="generar informe (IA): listado de atenciones")
    from apps.cumplimiento.models import Consentimiento
    return render(request, "ia/generar_informe.html", {
        "estudiantes": estudiantes, "estudiante": estudiante, "periodo": periodo, "periodos": servicios.PERIODOS,
        "sesiones": sesiones, "caso_abierto": caso_abierto, "tipos": servicios.TIPOS_INFORME,
        "secciones": servicios.SECCIONES, "secciones_defecto": servicios.SECCIONES_POR_DEFECTO,
        "disponible": servicios.DISPONIBLE, "conectado": servicios.agente_conectado(), "hoy": timezone.localdate(),
        "consentimiento": estudiante is not None and Consentimiento.vigente_para(estudiante, "uso_ia"),
        "recientes": SolicitudIA.objects.filter(solicitante=u).select_related("caso__estudiante")[:5]})


@require_POST
@permiso_requerido("ia.usar")
def solicitar(request):
    u = request.user
    casos = casos_visibles(u)
    estudiante = estudiantes_visibles(u).filter(casos__in=casos, pk=request.POST.get("estudiante") or 0).distinct().first()
    if estudiante is None:
        denegar(request, "solicitud de IA sobre un estudiante no visible")
    periodo = _periodo(request.POST.get("periodo", "3"))
    ids = [int(x) for x in request.POST.getlist("sesiones") if x.isdigit()]
    sesiones = list(_sesiones_disponibles(u, casos, estudiante, periodo).filter(pk__in=ids))
    volver = reverse("ia:generar_informe") + "?estudiante=%d&periodo=%d" % (estudiante.pk, periodo)
    if len(sesiones) != len(set(ids)):
        denegar(request, "solicitud de IA con atenciones no visibles")
    caso = max(sesiones, key=lambda s: s.fecha_hora).caso if sesiones else None
    try:
        sol = servicios.crear_solicitud(u, estudiante, caso, sesiones, request.POST.get("tipo", ""),
                                        request.POST.getlist("secciones"))
    except servicios.ErrorSolicitud as e:
        messages.error(request, str(e))
        return redirect(volver)
    return redirect("ia:solicitud", sol.pk)


def _solicitud(request, pk):
    sol = get_object_or_404(SolicitudIA.objects.select_related("caso__estudiante", "contenido"), pk=pk)
    if sol.solicitante_id != request.user.pk:
        denegar(request, "solicitud de IA de otra profesional")
    return sol


@require_GET
@permiso_requerido("ia.usar")
def solicitud(request, pk):
    sol = _solicitud(request, pk)
    servicios.mantener_cola()
    sol.refresh_from_db()
    if sol.contenido_id:
        registrar(request.user, "consulta", "contenido_ia", sol.contenido_id)
    from apps.evaluacion.models import Informe
    return render(request, "ia/solicitud.html", {
        "sol": sol, "estudiante": sol.caso.estudiante, "contenido": sol.contenido, "conectado": servicios.agente_conectado(),
        "posicion": SolicitudIA.objects.filter(estado="pendiente", fecha_creacion__lte=sol.fecha_creacion).count(),
        "tipos_ficha": Informe.TIPOS, "tipo_sugerido": servicios.TIPO_INFORME_FICHA.get(sol.tipo_informe, "seguimiento"),
        "motivos": RetroalimentacionIA.MOTIVOS, "en_espera": sol.estado in ("pendiente", "en_proceso")})


def _contenido(request, pk):
    contenido = get_object_or_404(ContenidoIA.objects.select_related("caso"), pk=pk)
    if contenido.solicitante_id != request.user.pk:
        denegar(request, "borrador de IA de otra profesional")
    return contenido


@require_POST
@permiso_requerido("ia.usar")
def validar(request, pk):
    contenido = _contenido(request, pk)
    if not request.user.tiene_permiso("informe.gestionar"):
        denegar(request, "validar borrador sin permiso informe.gestionar")
    if contenido.estado != "generado":
        messages.error(request, "Este borrador ya fue validado o descartado.")
        return redirect("ia:solicitud", contenido.solicitud.pk)
    try:
        informe = servicios.validar(request.user, contenido, request.POST.get("texto", ""), request.POST.get("tipo_ficha"))
    except servicios.ErrorSolicitud as e:
        messages.error(request, str(e))
        return redirect("ia:solicitud", contenido.solicitud.pk)
    messages.success(request, "Borrador validado. Quedó como informe en borrador en la ficha del caso.")
    return redirect("evaluacion:informe", informe.pk)


@require_POST
@permiso_requerido("ia.usar")
def descartar(request, pk):
    contenido = _contenido(request, pk)
    if contenido.estado == "generado":
        servicios.descartar(request.user, contenido)
        messages.success(request, "Borrador descartado. Puede redactar el informe de forma manual.")
    return redirect("ia:solicitud", contenido.solicitud.pk)


@require_POST
@permiso_requerido("ia.usar")
def retroalimentar(request, pk):
    contenido = _contenido(request, pk)
    try:
        servicios.retroalimentar(request.user, contenido, request.POST.get("motivo", ""), request.POST.get("comentario", ""))
        messages.success(request, "Gracias: la observación queda registrada para ajustar el Modelfile.")
    except Exception:  # ValidationError de motivo o comentario
        messages.error(request, "Indique el motivo y un comentario de al menos 10 caracteres.")
    return redirect("ia:solicitud", contenido.solicitud.pk)
