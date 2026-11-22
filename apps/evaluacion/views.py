from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.privacidad import datos_visibles
from apps.core.privacidad import mostrar as _mostrar
from apps.auditoria.servicios import registrar
from apps.casos.acceso import casos_visibles
from apps.casos.models import Caso
from apps.cuentas.permisos import denegar, permiso_requerido
from apps.estudiantes.acceso import estudiantes_visibles
from apps.estudiantes.models import Estudiante

from .forms import CerrarPlanForm, EntregaInformeForm, EvaluacionForm, InformeForm, ParticipacionForm, PlanForm
from .models import AvisoReevaluacion, EvaluacionDiagnostica, Informe, PlanApoyo


def _caso(request, pk):
    caso = get_object_or_404(Caso.objects.select_related("estudiante"), pk=pk)
    if not casos_visibles(request.user).filter(pk=pk).exists():
        denegar(request, "caso %d" % pk)
    return caso


def _evaluacion(request, pk):
    ev = get_object_or_404(EvaluacionDiagnostica.objects.select_related("caso", "caso__estudiante"), pk=pk)
    _caso(request, ev.caso_id)
    return ev


def _errores(request, error):
    for mensaje in getattr(error, "messages", [str(error)]):
        messages.error(request, mensaje)


# ------------------------------------------------------------------ evaluación diagnóstica integral (RF-05)
@permiso_requerido("evaluacion.gestionar")
def evaluacion_nueva(request, caso_pk):
    caso = _caso(request, caso_pk)
    form = EvaluacionForm(request.POST or None, caso=caso)
    if request.method == "POST" and form.is_valid():
        ev = form.save()
        registrar(request.user, "creacion", "evaluacion_diagnostica", ev.pk)
        messages.success(request, "Evaluación registrada. Agregue ahora a los profesionales participantes.")
        return redirect("evaluacion:detalle", ev.pk)
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "Evaluación diagnóstica integral — %s" % pv(caso.estudiante),
        "volver_url": reverse("casos:detalle", args=[caso.pk]),
        "ayuda": "Decreto 170: la evaluación es integral e interdisciplinaria. Para NEE transitorias la reevaluación "
                 "se programa a 2 años si deja la fecha vacía."})


@permiso_requerido("evaluacion.ver", "evaluacion.gestionar")
def evaluacion_detalle(request, pk):
    ev = _evaluacion(request, pk)
    registrar(request.user, "consulta", "evaluacion_diagnostica", ev.pk)
    return render(request, "evaluacion/detalle.html", {
        "ev": ev, "participaciones": ev.participaciones.select_related("usuario"), "planes": ev.planes.all(),
        "gestiona": request.user.tiene_permiso("evaluacion.gestionar") and ev.estado == "en_proceso"})


@permiso_requerido("evaluacion.gestionar")
@datos_visibles
def evaluacion_editar(request, pk):
    ev = _evaluacion(request, pk)
    if ev.estado == "cerrada":
        messages.error(request, "La evaluación está cerrada.")
        return redirect("evaluacion:detalle", ev.pk)
    form = EvaluacionForm(request.POST or None, instance=ev, caso=ev.caso)
    if request.method == "POST" and form.is_valid():
        form.save()
        registrar(request.user, "modificacion", "evaluacion_diagnostica", ev.pk)
        messages.success(request, "Evaluación actualizada.")
        return redirect("evaluacion:detalle", ev.pk)
    return render(request, "comun/formulario.html", {"form": form, "titulo": "Editar evaluación",
                                                     "volver_url": reverse("evaluacion:detalle", args=[ev.pk])})


@permiso_requerido("evaluacion.gestionar")
def participacion_nueva(request, pk):
    ev = _evaluacion(request, pk)
    form = ParticipacionForm(request.POST or None, evaluacion=ev, initial={"usuario": request.user.pk})
    if request.method == "POST" and form.is_valid():
        p = form.save()
        registrar(request.user, "creacion", "participacion_evaluacion", p.pk)
        messages.success(request, "Participación registrada.")
        return redirect("evaluacion:detalle", ev.pk)
    return render(request, "comun/formulario.html", {"form": form, "titulo": "Participación en la evaluación",
                                                     "volver_url": reverse("evaluacion:detalle", args=[ev.pk])})


@require_POST
@permiso_requerido("evaluacion.gestionar")
def evaluacion_cerrar(request, pk):
    ev = _evaluacion(request, pk)
    ev.estado = "cerrada"
    try:
        ev.full_clean()
    except ValidationError as e:
        _errores(request, e)
        return redirect("evaluacion:detalle", ev.pk)
    ev.save()
    registrar(request.user, "modificacion", "evaluacion_diagnostica", ev.pk, detalle="cierre")
    messages.success(request, "Evaluación cerrada." + (" Reevaluación programada para el %s." %
                                                      ev.fecha_reevaluacion.strftime("%d-%m-%Y") if ev.fecha_reevaluacion else ""))
    return redirect("evaluacion:detalle", ev.pk)


# ------------------------------------------------------------------ planes de apoyo (RF-07)
@permiso_requerido("plan.gestionar")
def plan_nuevo(request, estudiante_pk):
    estudiante = get_object_or_404(Estudiante, pk=estudiante_pk)
    if not estudiantes_visibles(request.user).filter(pk=estudiante.pk).exists():
        denegar(request, "estudiante %d" % estudiante.pk)
    form = PlanForm(request.POST or None, estudiante=estudiante)
    if request.method == "POST" and form.is_valid():
        plan = form.save()
        registrar(request.user, "creacion", "plan_apoyo", plan.pk)
        messages.success(request, "Plan de apoyo registrado.")
        return redirect("estudiantes:detalle", estudiante.pk)
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "Plan de apoyo — %s" % pv(estudiante),
        "volver_url": reverse("estudiantes:detalle", args=[estudiante.pk]),
        "ayuda": "Las adecuaciones las verá el profesor jefe; el detalle se guarda cifrado."})


def _plan(request, pk, **filtros):
    plan = get_object_or_404(PlanApoyo, pk=pk, **filtros)
    if not estudiantes_visibles(request.user).filter(pk=plan.estudiante_id).exists():
        denegar(request, "plan_apoyo %d" % plan.pk)
    return plan


@permiso_requerido("plan.gestionar")
@datos_visibles
def plan_editar(request, pk):
    plan = _plan(request, pk)
    if plan.estado != "vigente":
        messages.error(request, "Solo se editan planes vigentes.")
        return redirect("estudiantes:detalle", plan.estudiante_id)
    form = PlanForm(request.POST or None, instance=plan)
    if request.method == "POST" and form.is_valid():
        form.save()
        registrar(request.user, "modificacion", "plan_apoyo", plan.pk)
        messages.success(request, "Plan actualizado.")
        return redirect("estudiantes:detalle", plan.estudiante_id)
    return render(request, "comun/formulario.html", {"form": form, "titulo": "Editar %s" % plan,
                                                     "volver_url": reverse("estudiantes:detalle", args=[plan.estudiante_id])})


@permiso_requerido("plan.gestionar")
def plan_cerrar(request, pk):
    plan = _plan(request, pk, estado="vigente")
    form = CerrarPlanForm(request.POST or None, plan=plan)
    if request.method == "POST" and form.is_valid():
        plan.estado, plan.fecha_termino = "cerrado", form.cleaned_data["fecha_termino"]
        plan.full_clean()
        plan.save()
        registrar(request.user, "modificacion", "plan_apoyo", plan.pk, detalle="cierre")
        messages.success(request, "Plan cerrado.")
        return redirect("estudiantes:detalle", plan.estudiante_id)
    return render(request, "comun/formulario.html", {"form": form, "titulo": "Cerrar %s" % plan,
                                                     "volver_url": reverse("estudiantes:detalle", args=[plan.estudiante_id])})


# ------------------------------------------------------------------ informes (RF-06)
def _informe(request, pk):
    informe = get_object_or_404(Informe.objects.select_related("caso", "caso__estudiante", "contenido_ia"), pk=pk)
    _caso(request, informe.caso_id)
    return informe


@permiso_requerido("informe.gestionar")
def informe_nuevo(request, caso_pk):
    caso = _caso(request, caso_pk)
    form = InformeForm(request.POST or None, caso=caso)
    if request.method == "POST" and form.is_valid():
        informe = form.save()
        registrar(request.user, "creacion", "informe", informe.pk)
        messages.success(request, "Informe guardado como borrador.")
        return redirect("evaluacion:informe", informe.pk)
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "Nuevo informe — %s" % pv(caso.estudiante), "volver_url": reverse("casos:detalle", args=[caso.pk]),
        "ayuda": "También puede partir desde un borrador del copiloto de IA validado (menú del caso)."})


@permiso_requerido("informe.gestionar")
def informe_detalle(request, pk):
    informe = _informe(request, pk)
    registrar(request.user, "consulta", "informe", informe.pk)
    return render(request, "evaluacion/informe.html", {"informe": informe})


@permiso_requerido("informe.gestionar")
@datos_visibles
def informe_editar(request, pk):
    informe = _informe(request, pk)
    if informe.estado != "borrador":
        messages.error(request, "Solo se editan informes en borrador.")
        return redirect("evaluacion:informe", informe.pk)
    form = InformeForm(request.POST or None, instance=informe)
    if request.method == "POST" and form.is_valid():
        form.save()
        registrar(request.user, "modificacion", "informe", informe.pk)
        messages.success(request, "Informe actualizado.")
        return redirect("evaluacion:informe", informe.pk)
    return render(request, "comun/formulario.html", {"form": form, "titulo": "Editar informe",
                                                     "volver_url": reverse("evaluacion:informe", args=[informe.pk])})


@require_POST
@permiso_requerido("informe.gestionar")
def informe_validar(request, pk):
    informe = _informe(request, pk)
    if informe.estado != "borrador":
        return redirect("evaluacion:informe", informe.pk)
    informe.estado = "validado"
    try:
        informe.full_clean()
    except ValidationError as e:
        _errores(request, e)
        return redirect("evaluacion:informe", informe.pk)
    informe.save()
    registrar(request.user, "modificacion", "informe", informe.pk, detalle="validado")
    messages.success(request, "Informe validado.")
    return redirect("evaluacion:informe", informe.pk)


@permiso_requerido("informe.gestionar")
def informe_entregar(request, pk):
    informe = _informe(request, pk)
    if informe.estado != "validado":
        messages.error(request, "Solo se entregan informes validados.")
        return redirect("evaluacion:informe", informe.pk)
    form = EntregaInformeForm(request.POST or None, informe=informe)
    if request.method == "POST" and form.is_valid():
        informe.estado, informe.fecha_entrega = "entregado", form.cleaned_data["fecha_entrega"]
        informe.full_clean()
        informe.save()
        registrar(request.user, "modificacion", "informe", informe.pk, detalle="entregado")
        messages.success(request, "Entrega registrada.")
        return redirect("evaluacion:informe", informe.pk)
    return render(request, "comun/formulario.html", {"form": form, "titulo": "Registrar entrega del informe",
                                                     "volver_url": reverse("evaluacion:informe", args=[informe.pk])})


@require_POST
@permiso_requerido("informe.gestionar")
@transaction.atomic
def informe_descartar(request, pk):
    informe = _informe(request, pk)
    if informe.estado != "borrador":
        messages.error(request, "Solo se descartan informes en borrador.")
        return redirect("evaluacion:informe", informe.pk)
    caso_id = informe.caso_id
    registrar(request.user, "eliminacion", "informe", informe.pk)
    informe.delete()
    messages.success(request, "Borrador descartado.")
    return redirect("casos:detalle", caso_id)


# ------------------------------------------------------------------ avisos de reevaluación (RF-08)
@permiso_requerido("evaluacion.gestionar")
def avisos(request):
    lista = AvisoReevaluacion.objects.filter(destinatario=request.user).select_related("evaluacion__caso__estudiante")
    return render(request, "evaluacion/avisos.html", {"avisos": lista})


def pv(objeto):
    """Nombre para títulos y mensajes: iniciales si la sesión está en modo privado."""
    return _mostrar(str(objeto), "nombre")
