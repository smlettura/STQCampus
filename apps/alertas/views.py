from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.auditoria.servicios import registrar
from apps.casos.acceso import casos_visibles
from apps.cuentas.permisos import denegar, permiso_requerido

from . import servicios
from .acceso import alertas_visibles, es_destinatario, puede_gestionar, puede_ver
from .forms import AlertaForm, DenunciaForm, GestionForm, VincularCasoForm
from .models import AlertaRiesgo, Denuncia, Notificacion


def _alerta(request, pk):
    alerta = get_object_or_404(AlertaRiesgo.objects.select_related("estudiante", "estudiante__curso", "sede", "informante",
                                                                    "caso"), pk=pk)
    if not puede_ver(request.user, alerta):
        denegar(request, "alerta %d" % pk)
    return alerta


@permiso_requerido("alerta.registrar")
def registrar_alerta(request):
    form = AlertaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            alerta = form.save(commit=False)
            alerta.informante = request.user
            alerta.fecha_hora_registro = timezone.now()
            alerta.save()
            registrar(request.user, "creacion", "alerta_riesgo", alerta.pk)
            _, sin_responsable = servicios.notificar_alerta(alerta)
        if sin_responsable:
            messages.warning(request, "No se encontró un responsable con ese rol en la sede: se notificó a la Directora.")
        messages.success(request, "Alerta registrada y notificada. Guarde la constancia.")
        return redirect("alertas:constancia_registro", alerta.pk)
    return render(request, "alertas/registrar.html", {"form": form})


@permiso_requerido("alerta.registrar")
def constancia_registro(request, pk):
    alerta = _alerta(request, pk)
    if alerta.informante_id != request.user.pk and not request.user.tiene_permiso("alerta.ver_constancias"):
        denegar(request, "constancia alerta %d" % pk)
    notificaciones = alerta.notificaciones.select_related("destinatario").order_by("fecha_hora_envio")
    personas = {n.destinatario for n in notificaciones}
    reglas = {r.rol_responsable.nombre for r in servicios.reglas_aplicables(alerta)}
    return render(request, "alertas/constancia_registro.html", {"alerta": alerta, "notificaciones": notificaciones,
                                                                "roles": sorted(reglas), "personas": len(personas)})


@permiso_requerido("alerta.registrar", "alerta.gestionar", "alerta.ver_constancias")
def lista(request):
    qs = alertas_visibles(request.user).select_related("estudiante", "estudiante__curso", "sede", "informante")
    estado = request.GET.get("estado", "abiertas")
    if estado == "abiertas":
        qs = qs.exclude(estado="cerrada")
    elif estado in dict(AlertaRiesgo.ESTADOS):
        qs = qs.filter(estado=estado)
    sin_leer = set(Notificacion.objects.filter(destinatario=request.user, fecha_hora_lectura__isnull=True)
                   .values_list("alerta_id", flat=True))
    return render(request, "alertas/lista.html", {"alertas": qs, "estado": estado, "sin_leer": sin_leer,
                                                  "estados": AlertaRiesgo.ESTADOS, "ahora": timezone.now()})


@permiso_requerido("alerta.registrar", "alerta.gestionar", "alerta.ver_constancias")
def detalle(request, pk):
    alerta = _alerta(request, pk)
    u = request.user
    Notificacion.objects.filter(alerta=alerta, destinatario=u, fecha_hora_lectura__isnull=True).update(
        fecha_hora_lectura=timezone.now())
    registrar(u, "consulta", "alerta_riesgo", alerta.pk)
    ve_gestion = es_destinatario(u, alerta) or u.tiene_permiso("alerta.ver_constancias")
    denuncia = Denuncia.objects.filter(alerta=alerta).select_related("psicologa").first()
    return render(request, "alertas/detalle.html", {
        "alerta": alerta, "ve_gestion": ve_gestion, "es_informante": alerta.informante_id == u.pk,
        "gestiona": puede_gestionar(u, alerta) and alerta.estado != "cerrada",
        "gestiones": alerta.gestiones.select_related("responsable") if ve_gestion else [],
        "notificaciones": alerta.notificaciones.select_related("destinatario") if ve_gestion else [],
        "denuncia": denuncia,
        "puede_denunciar": u.tiene_permiso("denuncia.registrar") and u.tiene_rol("psicologa_denunciante")
        and denuncia is None and alerta.estado != "cerrada",
        "form_gestion": GestionForm(alerta=alerta, responsable=u),
        "form_caso": VincularCasoForm(alerta=alerta, casos=casos_visibles(u))
        if u.tiene_permiso("caso.gestionar") and not alerta.caso_id else None,
        "ahora": timezone.now()})


@permiso_requerido("alerta.gestionar")
def gestionar(request, pk):
    alerta = _alerta(request, pk)
    if not puede_gestionar(request.user, alerta) or request.method != "POST":
        denegar(request, "gestión alerta %d" % pk)
    form = GestionForm(request.POST, alerta=alerta, responsable=request.user)
    if form.is_valid():
        with transaction.atomic():
            gestion = form.save()
            nuevo_estado = "cerrada" if gestion.accion == "cierre" else (
                alerta.estado if alerta.estado == "denunciada" else "en_gestion")
            if nuevo_estado != alerta.estado:
                alerta.estado = nuevo_estado
                alerta.save(update_fields=["estado"])
            registrar(request.user, "creacion", "gestion_alerta", gestion.pk, detalle=gestion.accion)
            protocolo = None
            if gestion.accion == "protocolo_activado":
                from apps.convivencia.servicios import activar_desde_alerta
                protocolo = activar_desde_alerta(alerta, request.user, timezone.localtime(gestion.fecha_hora).date())
        messages.success(request, "Gestión registrada." + (" El protocolo quedó abierto en «Protocolos»." if protocolo else ""))
    else:
        for errores in form.errors.values():
            for e in errores:
                messages.error(request, e)
    return redirect("alertas:detalle", alerta.pk)


@permiso_requerido("denuncia.registrar")
def denunciar(request, pk):
    alerta = _alerta(request, pk)
    if hasattr(alerta, "denuncia"):
        messages.info(request, "La denuncia ya está registrada.")
        return redirect("alertas:detalle", alerta.pk)
    if not request.user.tiene_rol("psicologa_denunciante"):
        denegar(request, "denuncia alerta %d" % pk)
    form = DenunciaForm(request.POST or None, alerta=alerta, psicologa=request.user)
    if request.method == "POST" and form.is_valid():
        denuncia = servicios.registrar_denuncia(form.save(commit=False))
        if not denuncia.dentro_de_plazo:
            registrar(request.user, "modificacion", "denuncia", denuncia.pk, detalle="presentada fuera del plazo de 24 h")
        messages.success(request, "Denuncia registrada con constancia sellada. La Directora fue informada.")
        return redirect("alertas:detalle", alerta.pk)
    return render(request, "alertas/denunciar.html", {"form": form, "alerta": alerta, "ahora": timezone.now()})


@permiso_requerido("caso.gestionar")
def vincular_caso(request, pk):
    alerta = _alerta(request, pk)
    form = VincularCasoForm(request.POST or None, alerta=alerta, casos=casos_visibles(request.user))
    if request.method == "POST" and form.is_valid():
        alerta.caso = form.cleaned_data["caso"]
        alerta.full_clean()
        alerta.save(update_fields=["caso"])
        registrar(request.user, "modificacion", "alerta_riesgo", alerta.pk, detalle="vinculada a caso %d" % alerta.caso_id)
        messages.success(request, "Alerta vinculada al caso.")
    return redirect("alertas:detalle", alerta.pk)


@permiso_requerido("alerta.ver_constancias")
def constancias(request):
    """RF-14: constancias con su hash y verificación de integridad."""
    notifs = Notificacion.objects.select_related("alerta", "destinatario").order_by("-fecha_hora_envio")[:200]
    denuncias = Denuncia.objects.select_related("alerta", "psicologa")
    registrar(request.user, "consulta", "constancias", None)
    return render(request, "alertas/constancias.html", {"notificaciones": notifs, "denuncias": denuncias,
                                                        "volver_url": reverse("alertas:lista")})
