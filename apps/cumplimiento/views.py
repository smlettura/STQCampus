from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.auditoria.servicios import registrar
from apps.cuentas.permisos import denegar, permiso_requerido
from apps.estudiantes.acceso import estudiantes_visibles
from apps.estudiantes.models import Estudiante

from . import servicios
from .forms import (ConsentimientoForm, DecisionRetencionForm, RespuestaARCOForm, RevocarConsentimientoForm,
                    SolicitudARCOForm)
from .models import Consentimiento, RetencionEliminacion, SolicitudARCO


def _estudiante(request, pk):
    estudiante = get_object_or_404(Estudiante, pk=pk)
    if not estudiantes_visibles(request.user).filter(pk=pk).exists():
        denegar(request, "estudiante %d" % pk)
    return estudiante


# ------------------------------------------------------------------ consentimiento informado (RF-11)
@permiso_requerido("consentimiento.gestionar")
def consentimiento_nuevo(request, estudiante_pk):
    estudiante = _estudiante(request, estudiante_pk)
    if not estudiante.vinculos_apoderado.exists():
        messages.error(request, "El estudiante no tiene apoderados vinculados.")
        return redirect("estudiantes:detalle", estudiante.pk)
    form = ConsentimientoForm(request.POST or None, estudiante=estudiante)
    if request.method == "POST" and form.is_valid():
        c = form.save()
        registrar(request.user, "creacion", "consentimiento", c.pk)
        messages.success(request, "Consentimiento registrado.")
        return redirect("estudiantes:detalle", estudiante.pk)
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "Consentimiento informado — %s" % estudiante,
        "volver_url": reverse("estudiantes:detalle", args=[estudiante.pk]),
        "ayuda": "Registre el consentimiento firmado por el apoderado. Puede adjuntar la copia escaneada como documento "
                 "del caso y luego seleccionarla aquí."})


@permiso_requerido("consentimiento.gestionar")
def consentimiento_revocar(request, pk):
    c = get_object_or_404(Consentimiento, pk=pk, fecha_revocacion__isnull=True)
    _estudiante(request, c.estudiante_id)
    form = RevocarConsentimientoForm(request.POST or None, consentimiento=c)
    if request.method == "POST" and form.is_valid():
        c.fecha_revocacion = form.cleaned_data["fecha_revocacion"]
        c.full_clean()
        c.save()
        registrar(request.user, "modificacion", "consentimiento", c.pk, detalle="revocación")
        messages.success(request, "Revocación registrada.")
        return redirect("estudiantes:detalle", c.estudiante_id)
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "Revocar consentimiento: %s" % c.get_alcance_display(),
        "volver_url": reverse("estudiantes:detalle", args=[c.estudiante_id]),
        "advertencia": "Desde la revocación no podrán iniciarse nuevos tratamientos con este alcance."})


# ------------------------------------------------------------------ derechos ARCO+ (RF-12)
@permiso_requerido("arco.gestionar")
def arco_lista(request):
    lista = SolicitudARCO.objects.select_related("estudiante", "apoderado", "responsable")
    if request.GET.get("pendientes", "1") == "1":
        lista = lista.filter(estado__in=["recibida", "en_analisis"])
    return render(request, "cumplimiento/arco.html", {"solicitudes": lista, "hoy": timezone.localdate()})


@permiso_requerido("arco.gestionar")
def arco_nueva(request, estudiante_pk):
    estudiante = _estudiante(request, estudiante_pk)
    form = SolicitudARCOForm(request.POST or None, estudiante=estudiante, responsable=request.user)
    if request.method == "POST" and form.is_valid():
        s = form.save()
        registrar(request.user, "creacion", "solicitud_arco", s.pk)
        messages.success(request, "Solicitud registrada. Plazo de respuesta: %s." % s.fecha_limite.strftime("%d-%m-%Y"))
        return redirect("cumplimiento:arco")
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "Solicitud de derechos ARCO+ — %s" % estudiante,
        "volver_url": reverse("estudiantes:detalle", args=[estudiante.pk])})


@permiso_requerido("arco.gestionar")
def arco_detalle(request, pk):
    s = get_object_or_404(SolicitudARCO.objects.select_related("estudiante", "apoderado"), pk=pk)
    form = RespuestaARCOForm(request.POST or None, instance=s)
    if request.method == "POST" and form.is_valid():
        form.save()
        registrar(request.user, "modificacion", "solicitud_arco", s.pk, detalle=s.estado)
        messages.success(request, "Solicitud actualizada.")
        return redirect("cumplimiento:arco")
    return render(request, "cumplimiento/arco_detalle.html", {"s": s, "form": form})


@permiso_requerido("arco.gestionar")
def arco_exportar(request, pk):
    s = get_object_or_404(SolicitudARCO.objects.select_related("estudiante"), pk=pk)
    if s.tipo_derecho not in ("acceso", "portabilidad"):
        messages.error(request, "La exportación corresponde a solicitudes de acceso o portabilidad.")
        return redirect("cumplimiento:arco_detalle", s.pk)
    if s.estudiante is None:
        messages.error(request, "El expediente ya no existe.")
        return redirect("cumplimiento:arco")
    contenido = servicios.exportar_expediente(s.estudiante, request.user, request.user.tiene_permiso("caso.ver_equipo"))
    respuesta = HttpResponse(contenido, content_type="application/json; charset=utf-8")
    respuesta["Content-Disposition"] = 'attachment; filename="expediente_%d_%s.json"' % (s.estudiante_id,
                                                                                        timezone.localdate().isoformat())
    return respuesta


# ------------------------------------------------------------------ retención (RNF-10)
@permiso_requerido("retencion.ver", "retencion.autorizar")
def retenciones(request):
    lista = RetencionEliminacion.objects.select_related("estudiante", "autorizada_por")
    return render(request, "cumplimiento/retenciones.html", {"retenciones": lista})


@permiso_requerido("retencion.autorizar")
def retencion_decidir(request, pk):
    r = get_object_or_404(RetencionEliminacion.objects.select_related("estudiante"), pk=pk,
                          estado__in=["propuesta", "postergada"])
    if not request.user.tiene_rol("directora"):
        denegar(request, "retención %d" % pk)
    form = DecisionRetencionForm(request.POST or None, initial={"accion": r.accion})
    if request.method == "POST" and form.is_valid():
        try:
            servicios.autorizar(r, request.user, form.cleaned_data["accion"], form.cleaned_data["decision"] == "autorizar")
        except ValidationError as e:
            for m in e.messages:
                messages.error(request, m)
        else:
            messages.success(request, "Decisión registrada: %s." % r.get_estado_display().lower())
            return redirect("cumplimiento:retenciones")
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "Autorización de eliminación por retención", "volver_url": reverse("cumplimiento:retenciones"),
        "ayuda": "Expediente de %s. Plazo de 15 años cumplido el %s. La ejecución la realiza la tarea programada."
                 % (r.estudiante, r.fecha_vencimiento.strftime("%d-%m-%Y")),
        "advertencia": "La eliminación y la anonimización son irreversibles."})
