import datetime
import hmac

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


@login_required
def inicio(request):
    """Panel de inicio con las tareas pendientes según los permisos de cada rol."""
    from apps.alertas.models import Notificacion
    from apps.casos.models import Caso, Derivacion
    from apps.cumplimiento.models import RetencionEliminacion, SolicitudARCO
    from apps.estudiantes.acceso import estudiantes_visibles
    from apps.evaluacion.models import AvisoReevaluacion, EvaluacionDiagnostica

    u = request.user
    if u.tiene_permiso("caso.ver_equipo", "caso.ver_pie", "reportes.ver"):
        return redirect("casos:resumen")          # «Atención psicosocial › Resumen» del prototipo v1
    hoy = timezone.localdate()
    ctx = {"hoy": hoy}
    ctx["notificaciones"] = (Notificacion.objects.filter(destinatario=u, canal="plataforma")
                             .select_related("alerta").order_by("fecha_hora_lectura", "-fecha_hora_envio")[:6])
    if u.tiene_permiso("caso.gestionar"):
        pendientes = Derivacion.objects.filter(caso__isnull=True)
        mios = Caso.objects.filter(responsable=u).exclude(estado="cerrado")
        ctx["n_derivaciones"], ctx["n_mis_casos"] = pendientes.count(), mios.count()
        ctx["derivaciones_pendientes"] = pendientes.select_related("estudiante", "estudiante__curso", "derivante")[:8]
        ctx["mis_casos"] = mios.select_related("estudiante", "estudiante__curso")[:10]
    if u.tiene_permiso("caso.derivar") and not u.tiene_permiso("caso.gestionar"):
        # Quien deriva solo ve si su derivación fue recibida o atendida; nunca el contenido del caso.
        ctx["mis_derivaciones"] = Derivacion.objects.filter(derivante=u).select_related("estudiante")[:6]
    if u.tiene_permiso("evaluacion.gestionar"):
        avisos = AvisoReevaluacion.objects.filter(destinatario=u).exclude(estado="atendido")
        ctx["n_avisos"] = avisos.count()
        ctx["avisos"] = avisos.select_related("evaluacion__caso__estudiante")[:8]
        ctx["evaluaciones_en_proceso"] = EvaluacionDiagnostica.objects.filter(estado="en_proceso").select_related(
            "caso__estudiante").count()
    if u.tiene_permiso("alerta.gestionar") or u.tiene_permiso("alerta.ver_constancias"):
        from apps.alertas.acceso import alertas_visibles
        ctx["alertas_abiertas"] = alertas_visibles(u).exclude(estado="cerrada").count()
    if u.tiene_permiso("denuncia.registrar"):
        from apps.alertas.models import AlertaRiesgo
        ctx["denuncias_pendientes"] = AlertaRiesgo.objects.filter(posible_delito=True, denuncia__isnull=True).exclude(
            estado="cerrada").count()
    if u.tiene_permiso("retencion.autorizar"):
        ctx["retenciones_propuestas"] = RetencionEliminacion.objects.filter(estado="propuesta").count()
    if u.tiene_permiso("arco.gestionar"):
        ctx["arco_pendientes"] = SolicitudARCO.objects.filter(estado__in=["recibida", "en_analisis"]).count()
    if u.tiene_permiso("estudiante.ver_curso") and not u.tiene_permiso("estudiante.ver_todos"):
        ctx["mis_estudiantes"] = estudiantes_visibles(u).count()
    return render(request, "core/inicio.html", ctx)


def error_403(request, exception=None):
    return render(request, "errores/403.html", status=403)


def error_404(request, exception=None):
    return render(request, "errores/404.html", status=404)


@csrf_exempt
@require_POST
def tarea_programada(request, nombre):
    """Punto HTTP de respaldo para las tareas programadas (requiere TAREAS_TOKEN). En AWS las tareas se ejecutan con
    el comando «ejecutar_tarea», que dispara EventBridge Scheduler mediante Systems Manager."""
    token = getattr(settings, "TAREAS_TOKEN", "")
    enviado = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token or not hmac.compare_digest(token, enviado):
        raise Http404
    from apps.auditoria.servicios import registrar
    from apps.core.tareas import TAREAS

    if nombre not in TAREAS:
        raise Http404
    resultado = TAREAS[nombre]()
    registrar(None, "modificacion", "tarea_programada", None, detalle=nombre)
    return JsonResponse(resultado)
