from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.privacidad import datos_visibles
from apps.core.privacidad import mostrar as _mostrar
from apps.auditoria.servicios import registrar
from apps.cuentas.permisos import denegar, permiso_requerido
from apps.estudiantes.acceso import estudiantes_visibles
from apps.estudiantes.models import Estudiante

from . import servicios
from . import arco
from .forms import (BloqueoForm, ConsentimientoForm, DecisionRetencionForm, OposicionForm, RectificacionApoderadoForm,
                    RectificacionEstudianteForm, RespuestaARCOForm, RevocarConsentimientoForm, SolicitudARCOForm,
                    SupresionForm)
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
        "form": form, "titulo": "Consentimiento informado — %s" % pv(estudiante),
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
def _solicitud(pk):
    return get_object_or_404(SolicitudARCO.objects.select_related("estudiante", "estudiante__curso", "apoderado",
                                                                  "responsable"), pk=pk)


def _accion_valida(request, s, accion):
    if not arco.puede(s, accion):
        messages.error(request, "Esa acción no corresponde a una solicitud de %s." % s.get_tipo_derecho_display().lower())
        return False
    if s.estado not in arco.PENDIENTES:
        messages.error(request, "La solicitud ya está cerrada.")
        return False
    return True


@permiso_requerido("arco.gestionar")
def arco_lista(request):
    hoy = timezone.localdate()
    todas = SolicitudARCO.objects.select_related("estudiante", "estudiante__curso", "apoderado", "responsable")
    pendientes = todas.filter(estado__in=arco.PENDIENTES)
    kpis = {"pendientes": pendientes.count(), "vencidas": pendientes.filter(fecha_limite__lt=hoy).count(),
            "por_vencer": pendientes.filter(fecha_limite__gte=hoy, fecha_limite__lte=hoy + timedelta(days=5)).count(),
            "cerradas_mes": todas.filter(estado__in=["respondida", "rechazada"], fecha_respuesta__year=hoy.year,
                                         fecha_respuesta__month=hoy.month).count()}
    vista = request.GET.get("vista", "pendientes")
    lista = {"pendientes": pendientes, "vencidas": pendientes.filter(fecha_limite__lt=hoy),
             "cerradas": todas.exclude(estado__in=arco.PENDIENTES)}.get(vista, todas)
    derecho = request.GET.get("derecho", "")
    if derecho in dict(SolicitudARCO.DERECHOS):
        lista = lista.filter(tipo_derecho=derecho)
    q = " ".join(request.GET.get("q", "").split())[:60]
    if q:
        ids = estudiantes_visibles(request.user).buscar(q).values_list("pk", flat=True)
        lista = lista.filter(estudiante_id__in=list(ids))
    return render(request, "cumplimiento/arco.html", {
        "solicitudes": lista, "hoy": hoy, "kpis": kpis, "vista": vista, "derecho": derecho, "q": q,
        "derechos": SolicitudARCO.DERECHOS})


@permiso_requerido("arco.gestionar")
def arco_buscar(request):
    """«Nueva solicitud» desde el panel: el buscador lleva al formulario del estudiante elegido."""
    pk = request.GET.get("estudiante", "")
    if pk.isdigit():
        return redirect("cumplimiento:arco_nueva", int(pk))
    messages.warning(request, "Elija un estudiante de la lista desplegable.")
    return redirect("cumplimiento:arco")


@permiso_requerido("arco.gestionar")
def arco_nueva(request, estudiante_pk):
    estudiante = _estudiante(request, estudiante_pk)
    if not estudiante.vinculos_apoderado.exists():
        messages.error(request, "El estudiante no tiene apoderados vinculados: vincule al titular antes de registrar la solicitud.")
        return redirect("estudiantes:detalle", estudiante.pk)
    form = SolicitudARCOForm(request.POST or None, estudiante=estudiante, responsable=request.user)
    if request.method == "POST" and form.is_valid():
        s = form.save()
        arco.anotar(s, request.user, "registro")
        registrar(request.user, "creacion", "solicitud_arco", s.pk)
        messages.success(request, "Solicitud registrada. Plazo de respuesta: %s." % s.fecha_limite.strftime("%d-%m-%Y"))
        return redirect("cumplimiento:arco_detalle", s.pk)
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "Solicitud de derechos ARCO+ — %s" % pv(estudiante),
        "volver_url": reverse("cumplimiento:arco"),
        "ayuda": "Registre la solicitud el mismo día en que llega. El plazo de respuesta se calcula automáticamente."})


@permiso_requerido("arco.gestionar")
def arco_detalle(request, pk):
    s = _solicitud(pk)
    form = RespuestaARCOForm(request.POST or None, instance=s)
    if request.method == "POST" and form.is_valid():
        arco.responder(s, request.user, form)
        messages.success(request, "Respuesta registrada. Puede imprimir la carta para el titular.")
        return redirect("cumplimiento:arco_detalle", s.pk)
    from .models import BloqueoTratamiento, RetencionEliminacion
    return render(request, "cumplimiento/arco_detalle.html", {
        "s": s, "form": form, "acciones": s.acciones.select_related("usuario"),
        "puede": {a: arco.puede(s, a) for a in ("exportar", "informe_acceso", "rectificar", "suprimir", "oponerse", "bloquear")},
        "abierta": s.estado in arco.PENDIENTES,
        "bloqueo": BloqueoTratamiento.objects.filter(estudiante=s.estudiante, fecha_termino__isnull=True).first(),
        "supresion": RetencionEliminacion.objects.filter(solicitud_arco=s).first(),
        "form_bloqueo": BloqueoForm(), "hoy": timezone.localdate()})


@permiso_requerido("arco.gestionar")
@require_POST
def arco_analizar(request, pk):
    s = _solicitud(pk)
    arco.iniciar_analisis(s, request.user)
    messages.info(request, "Solicitud en análisis.")
    return redirect("cumplimiento:arco_detalle", s.pk)


@permiso_requerido("arco.gestionar")
def arco_exportar(request, pk):
    s = _solicitud(pk)
    if not arco.puede(s, "exportar"):
        messages.error(request, "La exportación corresponde a solicitudes de acceso o portabilidad.")
        return redirect("cumplimiento:arco_detalle", s.pk)
    contenido = servicios.exportar_expediente(s.estudiante, request.user, request.user.tiene_permiso("caso.ver_equipo"))
    arco.registrar_exportacion(s, request.user)
    respuesta = HttpResponse(contenido, content_type="application/json; charset=utf-8")
    respuesta["Content-Disposition"] = 'attachment; filename="expediente_%d_%s.json"' % (s.estudiante_id,
                                                                                        timezone.localdate().isoformat())
    return respuesta


@permiso_requerido("arco.gestionar")
def arco_informe_acceso(request, pk):
    """Derecho de acceso: informe legible e imprimible con todos los datos que trata la plataforma."""
    s = _solicitud(pk)
    if not arco.puede(s, "informe_acceso"):
        messages.error(request, "El informe de acceso corresponde a solicitudes de acceso.")
        return redirect("cumplimiento:arco_detalle", s.pk)
    clinico = request.user.tiene_permiso("caso.ver_equipo")
    datos = servicios.datos_expediente(s.estudiante, clinico)
    arco.registrar_exportacion(s, request.user, "informe_acceso")
    registrar(request.user, "exportacion", "estudiante", s.estudiante_id,
              detalle="informe de acceso ARCO+ %d (%s)" % (s.pk, "completo" if clinico else "administrativo"))
    return render(request, "cumplimiento/arco_acceso.html", {"s": s, "d": datos, "clinico": clinico, "hoy": timezone.localdate()})


@permiso_requerido("arco.gestionar")
@datos_visibles
def arco_rectificar(request, pk):
    s = _solicitud(pk)
    if not _accion_valida(request, s, "rectificar"):
        return redirect("cumplimiento:arco_detalle", s.pk)
    f_est = RectificacionEstudianteForm(request.POST or None, instance=s.estudiante)
    f_apo = RectificacionApoderadoForm(request.POST or None, instance=s.apoderado)
    if request.method == "POST" and f_est.is_valid() and f_apo.is_valid():
        try:
            cambiados = arco.rectificar(s, request.user, f_est, f_apo)
        except ValidationError as e:
            messages.warning(request, " ".join(e.messages))
        else:
            messages.success(request, "Rectificación aplicada (%d campo%s). Registre la respuesta al titular."
                             % (len(cambiados), "" if len(cambiados) == 1 else "s"))
            return redirect("cumplimiento:arco_detalle", s.pk)
    return render(request, "cumplimiento/arco_rectificar.html", {"s": s, "f_est": f_est, "f_apo": f_apo})


@permiso_requerido("arco.gestionar")
def arco_suprimir(request, pk):
    s = _solicitud(pk)
    if not _accion_valida(request, s, "suprimir"):
        return redirect("cumplimiento:arco_detalle", s.pk)
    form = SupresionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            arco.proponer_supresion(s, request.user, form.cleaned_data["accion"])
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
        else:
            messages.success(request, "Supresión propuesta a la Directora. Se ejecuta solo cuando ella la autorice.")
        return redirect("cumplimiento:arco_detalle", s.pk)
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "Supresión de datos — %s" % pv(s.estudiante),
        "volver_url": reverse("cumplimiento:arco_detalle", args=[s.pk]),
        "ayuda": "La supresión se propone a la Directora, responsable del tratamiento, que la autoriza en «Retención». "
                 "Si existe una obligación legal de conservar el expediente, rechace la solicitud con ese fundamento.",
        "advertencia": "Al ejecutarse, la supresión elimina también esta solicitud: registre antes la respuesta al titular."})


@permiso_requerido("arco.gestionar")
def arco_oponerse(request, pk):
    s = _solicitud(pk)
    if not _accion_valida(request, s, "oponerse"):
        return redirect("cumplimiento:arco_detalle", s.pk)
    form = OposicionForm(request.POST or None, estudiante=s.estudiante)
    if not form.fields["alcances"].choices:
        messages.warning(request, "El estudiante no tiene consentimientos vigentes a los que oponerse.")
        return redirect("cumplimiento:arco_detalle", s.pk)
    if request.method == "POST" and form.is_valid():
        try:
            revocados = arco.oponerse(s, request.user, form.cleaned_data["alcances"])
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
        else:
            messages.success(request, "Oposición aplicada: %d consentimiento%s revocado%s."
                             % (len(revocados), "" if len(revocados) == 1 else "s", "" if len(revocados) == 1 else "s"))
        return redirect("cumplimiento:arco_detalle", s.pk)
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "Oposición al tratamiento — %s" % pv(s.estudiante),
        "volver_url": reverse("cumplimiento:arco_detalle", args=[s.pk]),
        "ayuda": "Desde hoy no se podrán iniciar tratamientos con los alcances revocados (por ejemplo, el copiloto de IA)."})


@permiso_requerido("arco.gestionar")
@require_POST
def arco_bloquear(request, pk):
    s = _solicitud(pk)
    if not _accion_valida(request, s, "bloquear"):
        return redirect("cumplimiento:arco_detalle", s.pk)
    form = BloqueoForm(request.POST)
    if form.is_valid():
        try:
            arco.bloquear(s, request.user, form.cleaned_data["motivo"])
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
        else:
            messages.success(request, "Tratamiento bloqueado: se suspende el copiloto de IA y las nuevas evaluaciones.")
    else:
        messages.error(request, "Indique el motivo del bloqueo.")
    return redirect("cumplimiento:arco_detalle", s.pk)


@permiso_requerido("arco.gestionar")
@require_POST
def arco_desbloquear(request, pk):
    s = _solicitud(pk)
    try:
        arco.desbloquear(s, request.user)
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    else:
        messages.success(request, "Bloqueo levantado.")
    return redirect("cumplimiento:arco_detalle", s.pk)


@permiso_requerido("arco.gestionar")
def arco_carta(request, pk):
    """Carta de respuesta imprimible para el titular."""
    s = _solicitud(pk)
    if s.estado not in ("respondida", "rechazada"):
        messages.error(request, "Registre primero la respuesta.")
        return redirect("cumplimiento:arco_detalle", s.pk)
    return render(request, "cumplimiento/arco_carta.html", {"s": s, "acciones": s.acciones.all()})


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


def pv(objeto):
    """Nombre para títulos y mensajes: iniciales si la sesión está en modo privado."""
    return _mostrar(str(objeto), "nombre")
