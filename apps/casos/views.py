from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.auditoria.servicios import registrar
from apps.core.avisos import avisar_al_confirmar
from apps.core.validadores import TIPOS_MIME
from apps.core.filtros import Filtros
from apps.cuentas.permisos import denegar, permiso_requerido
from apps.estudiantes.acceso import estudiantes_visibles
from apps.estudiantes.models import Estudiante

from . import almacenamiento
from .acceso import casos_visibles, puede_gestionar, puede_ver_notas
from .forms import AbrirCasoForm, AtencionForm, CasoNuevoForm, CerrarCasoForm, DerivacionForm, DocumentoForm, HitoForm
from .models import Caso, Derivacion, Documento, SesionSeguimiento
from .servicios import atenciones_previas, casos_urgentes, con_ultima_urgencia, linea_de_tiempo


def _caso_visible(request, pk, gestionar=False):
    caso = get_object_or_404(Caso.objects.select_related("estudiante", "estudiante__curso", "responsable"), pk=pk)
    if not casos_visibles(request.user).filter(pk=pk).exists() or (gestionar and not puede_gestionar(request.user, caso)):
        denegar(request, "caso %d" % pk)
    return caso


# ------------------------------------------------------------------ derivación (RF-01, BPMN B1)
@permiso_requerido("caso.derivar")
def derivar(request):
    form = DerivacionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            derivacion = form.save(commit=False)
            derivacion.derivante = request.user
            derivacion.save()
            registrar(request.user, "creacion", "derivacion", derivacion.pk)
            from apps.alertas.servicios import usuarios_con_rol
            equipo = list(usuarios_con_rol("psicologa")) + list(usuarios_con_rol("asistente_social"))
            avisar_al_confirmar({u.pk: u for u in equipo}.values(), "Nueva derivación al equipo psicosocial",
                                reverse("casos:derivaciones"))
        messages.success(request, "Derivación registrada. El equipo psicosocial fue notificado.")
        return redirect("core:inicio")
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "Derivar al equipo psicosocial", "volver_url": reverse("core:inicio"),
        "ayuda": "Si observa una situación de riesgo para el estudiante, use «Registrar alerta de riesgo»: "
                 "tiene un flujo distinto con plazos legales.", "boton": "Registrar derivación"})


@permiso_requerido("caso.gestionar")
def derivaciones(request):
    pendientes = Derivacion.objects.filter(caso__isnull=True).select_related("estudiante", "estudiante__curso", "derivante")
    procesadas = Derivacion.objects.filter(caso__isnull=False).select_related("estudiante", "caso", "derivante")[:20]
    return render(request, "casos/derivaciones.html", {"pendientes": pendientes, "procesadas": procesadas})


@permiso_requerido("caso.gestionar")
def abrir_desde_derivacion(request, pk):
    derivacion = get_object_or_404(Derivacion.objects.select_related("estudiante"), pk=pk, caso__isnull=True)
    registrar(request.user, "consulta", "derivacion", derivacion.pk)
    form = AbrirCasoForm(request.POST or None, estudiante=derivacion.estudiante,
                         fecha_minima=timezone.localtime(derivacion.fecha_hora).date(),
                         initial={"responsable": request.user.pk})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            caso = form.save()
            derivacion.caso = caso
            derivacion.save(update_fields=["caso"])
            registrar(request.user, "creacion", "caso", caso.pk, detalle="desde derivación %d" % derivacion.pk)
        messages.success(request, "Caso abierto.")
        return redirect("casos:detalle", caso.pk)
    return render(request, "casos/abrir.html", {"form": form, "derivacion": derivacion})


@permiso_requerido("caso.gestionar")
def nuevo(request):
    inicial = {"responsable": request.user.pk}
    if request.GET.get("estudiante", "").isdigit():
        inicial["estudiante"] = int(request.GET["estudiante"])
    form = CasoNuevoForm(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        caso = form.save()
        registrar(request.user, "creacion", "caso", caso.pk)
        messages.success(request, "Caso abierto.")
        return redirect("casos:detalle", caso.pk)
    return render(request, "comun/formulario.html", {"form": form, "titulo": "Abrir caso sin derivación",
                                                     "volver_url": reverse("casos:lista")})


# ------------------------------------------------------------------ casos
@permiso_requerido("caso.ver_equipo", "caso.ver_pie")
def lista(request):
    """«Fichas de estudiantes» del prototipo v1: casos del equipo psicosocial con su última atención."""
    visibles = casos_visibles(request.user)
    qs = con_ultima_urgencia(visibles).select_related("estudiante", "estudiante__curso", "responsable").annotate(
        ultima_atencion=Max("sesiones__fecha_hora", filter=Q(sesiones__estado="registrada")),
        n_atenciones=Count("sesiones", filter=Q(sesiones__estado="registrada")))
    estado = request.GET.get("estado", "activos")
    if estado == "activos":
        qs = qs.exclude(estado="cerrado")
    elif estado == "urgentes":
        qs = qs.exclude(estado="cerrado").filter(ultima_urgencia="alta")
    elif estado in dict(Caso.ESTADOS):
        qs = qs.filter(estado=estado)
    tipo = request.GET.get("tipo")
    if tipo in dict(Caso.TIPOS_PROCESO):
        qs = qs.filter(tipo_proceso=tipo)
    if request.GET.get("mios") == "1":
        qs = qs.filter(responsable=request.user)
    q = " ".join(request.GET.get("q", "").split())
    if q:
        qs = qs.filter(estudiante__in=Estudiante.objects.buscar(q))
    conteo = {"activos": visibles.exclude(estado="cerrado").count(), "urgentes": casos_urgentes(visibles).count(),
              "cerrado": visibles.filter(estado="cerrado").count(), "todos": visibles.count()}
    pagina = Paginator(qs.order_by("-ultima_atencion", "-fecha_apertura"), 25).get_page(request.GET.get("pagina"))
    return render(request, "casos/lista.html", {
        "pagina": pagina, "estado": estado, "tipo": tipo, "q": q, "conteo": conteo, "tipos": Caso.TIPOS_PROCESO,
        "accion_barra": {"texto": "Nueva atención", "url": reverse("casos:registrar_atencion")}
        if request.user.tiene_permiso("caso.gestionar") else None})


@permiso_requerido("caso.ver_equipo", "caso.ver_pie")
def detalle(request, pk):
    caso = _caso_visible(request, pk)
    u = request.user
    registrar(u, "consulta", "caso", caso.pk)
    return render(request, "casos/detalle.html", {
        "caso": caso, "linea": linea_de_tiempo(caso, u), "ve_notas": puede_ver_notas(u, caso),
        "gestiona": puede_gestionar(u, caso) and not caso.cerrado,
        "evaluaciones": caso.evaluaciones.all(), "informes": caso.informes.all(),
        "documentos": caso.documentos.all(), "derivaciones": caso.derivaciones.select_related("derivante"),
        "estudiante_visible": estudiantes_visibles(u).filter(pk=caso.estudiante_id).exists()})


def _formulario_caso(request, pk, form_class, titulo, entidad, **extra):
    caso = _caso_visible(request, pk, gestionar=True)
    if caso.cerrado:
        messages.error(request, "El caso está cerrado.")
        return redirect("casos:detalle", caso.pk)
    form = form_class(request.POST or None, caso=caso)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            obj = form.save()
            if caso.estado == "abierto":
                caso.estado = "seguimiento"
                caso.save(update_fields=["estado"])
            registrar(request.user, "creacion", entidad, obj.pk, detalle="caso %d" % caso.pk)
        messages.success(request, "%s registrado." % titulo)
        return redirect("casos:detalle", caso.pk)
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "%s — %s" % (titulo, caso.estudiante), "volver_url": reverse("casos:detalle", args=[caso.pk]),
        **extra})


@permiso_requerido("caso.gestionar")
def sesion_nueva(request, pk):
    caso = _caso_visible(request, pk, gestionar=True)
    return redirect(reverse("casos:registrar_atencion") + "?estudiante=%d&caso=%d" % (caso.estudiante_id, caso.pk))


@permiso_requerido("caso.gestionar")
def hito_nuevo(request, pk):
    return _formulario_caso(request, pk, HitoForm, "Hito", "hito")


@permiso_requerido("caso.gestionar")
def documento_subir(request, pk):
    caso = _caso_visible(request, pk, gestionar=True)
    form = DocumentoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            doc = almacenamiento.guardar_adjunto(form.cleaned_data["archivo"], caso, form.cleaned_data["tipo"])
            registrar(request.user, "creacion", "documento", doc.pk, detalle="sha256 %s" % doc.hash_sha256)
        messages.success(request, "Documento adjuntado y cifrado.")
        return redirect("casos:detalle", caso.pk)
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "Adjuntar documento — %s" % caso.estudiante, "multipart": True,
        "volver_url": reverse("casos:detalle", args=[caso.pk]), "boton": "Adjuntar"})


@permiso_requerido("caso.ver_equipo", "caso.ver_pie")
def documento_descargar(request, pk):
    doc = get_object_or_404(Documento.objects.select_related("caso"), pk=pk)
    _caso_visible(request, doc.caso_id)
    try:
        datos = almacenamiento.leer_adjunto(doc)
    except Exception:
        registrar(request.user, "acceso_denegado", "documento", doc.pk, detalle="integridad o cifrado inválido")
        messages.error(request, "No se pudo abrir el documento: su integridad no pudo verificarse.")
        return redirect("casos:detalle", doc.caso_id)
    registrar(request.user, "exportacion", "documento", doc.pk)
    extension = "." + doc.nombre_archivo.rsplit(".", 1)[-1].lower() if "." in doc.nombre_archivo else ""
    respuesta = HttpResponse(datos, content_type=TIPOS_MIME.get(extension, "application/octet-stream"))
    respuesta["Content-Disposition"] = 'attachment; filename="%s"' % doc.nombre_archivo.replace('"', "")
    return respuesta


@permiso_requerido("caso.gestionar")
def cerrar(request, pk):
    caso = _caso_visible(request, pk, gestionar=True)
    if caso.cerrado:
        return redirect("casos:detalle", caso.pk)
    form = CerrarCasoForm(request.POST or None, caso=caso)
    if request.method == "POST" and form.is_valid():
        caso.estado = "cerrado"
        caso.fecha_cierre = form.cleaned_data["fecha_cierre"]
        caso.fecha_fin_retencion = caso.calcular_fin_retencion()
        caso.full_clean()
        caso.save()
        registrar(request.user, "modificacion", "caso", caso.pk, detalle="cierre; retención hasta %s" % caso.fecha_fin_retencion)
        messages.success(request, "Caso cerrado. Se conservará hasta el %s (15 años)." % caso.fecha_fin_retencion.strftime("%d-%m-%Y"))
        return redirect("casos:detalle", caso.pk)
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "Cerrar caso — %s" % caso.estudiante, "volver_url": reverse("casos:detalle", args=[caso.pk]),
        "boton": "Cerrar caso", "advertencia": "Un caso cerrado no admite nuevas sesiones ni hitos."})


@require_POST
@permiso_requerido("caso.gestionar")
def reabrir(request, pk):
    caso = _caso_visible(request, pk, gestionar=True)
    if caso.cerrado:
        caso.estado, caso.fecha_cierre, caso.fecha_fin_retencion = "seguimiento", None, None
        try:
            caso.full_clean()
        except Exception as e:  # p. ej., ya existe otro caso abierto del mismo tipo
            messages.error(request, "; ".join(getattr(e, "messages", [str(e)])))
            return redirect("casos:detalle", caso.pk)
        caso.save()
        registrar(request.user, "modificacion", "caso", caso.pk, detalle="reapertura")
        messages.success(request, "Caso reabierto.")
    return redirect("casos:detalle", caso.pk)


# ------------------------------------------------------------------ resumen y registrar atención (prototipo v1)
@permiso_requerido("caso.ver_equipo", "caso.ver_pie", "reportes.ver")
def resumen(request):
    from .resumen import datos_resumen
    f = Filtros(request, usar=("anio", "mes", "curso"))
    return render(request, "casos/resumen.html", {
        **f.contexto(), **datos_resumen(request.user, f),
        "accion_barra": {"texto": "Nueva atención", "url": reverse("casos:registrar_atencion")}
        if request.user.tiene_permiso("caso.gestionar") else None})


def _casos_para_atencion(usuario, estudiante):
    return casos_visibles(usuario).filter(estudiante=estudiante).exclude(estado="cerrado").order_by("-fecha_apertura")


@permiso_requerido("caso.gestionar")
def registrar_atencion(request):
    u = request.user
    borrador = None
    if request.GET.get("borrador", "").isdigit():
        borrador = get_object_or_404(SesionSeguimiento.objects.select_related("caso__estudiante"),
                                     pk=int(request.GET["borrador"]), estado="borrador", profesional=u)
        estudiante = borrador.caso.estudiante
    else:
        estudiante = None
        if request.GET.get("estudiante", "").isdigit():
            estudiante = get_object_or_404(estudiantes_visibles(u).select_related("curso"), pk=int(request.GET["estudiante"]))
    if estudiante is None:
        q = " ".join(request.GET.get("q", "").split())
        resultados = estudiantes_visibles(u).activos().buscar(q).select_related("curso")[:12] if q else None
        mis_casos = (casos_visibles(u).filter(responsable=u).exclude(estado="cerrado")
                     .select_related("estudiante", "estudiante__curso")[:8])
        return render(request, "casos/registrar_atencion.html", {"q": q, "resultados": resultados, "mis_casos": mis_casos,
                                                                 "hoy": timezone.localdate()})
    if not estudiante.activo and borrador is None:
        messages.error(request, "%s no está activo: no se pueden registrar atenciones nuevas." % estudiante)
        return redirect("estudiantes:detalle", estudiante.pk)

    casos = _casos_para_atencion(u, estudiante)
    if request.GET.get("caso", "").isdigit() and borrador is None:
        elegido = casos.filter(pk=int(request.GET["caso"]))
        casos = elegido if elegido.exists() else casos
    accion = request.POST.get("accion", "registrar")
    estado = "borrador" if accion == "borrador" else "registrada"
    form = AtencionForm(request.POST or None, instance=borrador, casos=None if borrador else casos, profesional=u,
                        estado=estado)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            sesion = form.save(commit=False)
            caso_nuevo = None
            if not sesion.caso_id:
                # Sin caso abierto: se abre uno de seguimiento psicosocial a cargo de quien registra la atención.
                caso_nuevo = Caso(estudiante=estudiante, tipo_proceso="seguimiento", responsable=u,
                                  fecha_apertura=min(timezone.localdate(), timezone.localtime(sesion.fecha_hora).date()),
                                  tipo_atencion=sesion.get_tipo_atencion_display())
                try:
                    caso_nuevo.full_clean()
                except ValidationError as e:
                    for m in e.messages:
                        messages.error(request, m)
                    return redirect(reverse("casos:registrar_atencion") + "?estudiante=%d" % estudiante.pk)
                caso_nuevo.save()
                registrar(u, "creacion", "caso", caso_nuevo.pk, detalle="abierto al registrar una atención")
                sesion.caso = caso_nuevo
            if not puede_gestionar(u, sesion.caso):
                denegar(request, "caso %d" % sesion.caso_id)
            sesion.estado = estado
            sesion.save()
            if estado == "registrada" and sesion.caso.estado == "abierto":
                sesion.caso.estado = "seguimiento"
                sesion.caso.save(update_fields=["estado"])
            registrar(u, "modificacion" if borrador else "creacion", "sesion_seguimiento", sesion.pk,
                      detalle="caso %d · %s" % (sesion.caso_id, estado))
        if estado == "borrador":
            messages.success(request, "Borrador guardado. Puede retomarlo desde «Atenciones anteriores».")
            return redirect(reverse("casos:registrar_atencion") + "?borrador=%d" % sesion.pk)
        messages.success(request, "Atención registrada%s." % (" y caso de seguimiento abierto" if caso_nuevo else ""))
        return redirect("casos:detalle", sesion.caso_id)
    caso_actual = borrador.caso if borrador else (casos.first() if casos.count() == 1 else None)
    return render(request, "casos/registrar_atencion.html", {
        "form": form, "e": estudiante, "borrador": borrador, "casos": casos, "caso_actual": caso_actual,
        "previas": atenciones_previas(estudiante, u), "hoy": timezone.localdate(),
        "en_pie": estudiante.en_pie, "en_seguimiento": casos.exists()})


@require_POST
@permiso_requerido("caso.gestionar")
def descartar_borrador(request, pk):
    sesion = get_object_or_404(SesionSeguimiento, pk=pk, estado="borrador", profesional=request.user)
    estudiante_id = sesion.caso.estudiante_id
    registrar(request.user, "eliminacion", "sesion_seguimiento", sesion.pk, detalle="borrador descartado")
    sesion.delete()
    messages.info(request, "Borrador descartado.")
    return redirect(reverse("casos:registrar_atencion") + "?estudiante=%d" % estudiante_id)
