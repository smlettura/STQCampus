"""Pantallas «Convivencia», «Protocolos», «Plan de gestión» e «Indicadores» del prototipo v1."""
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe

from apps.auditoria.servicios import registrar
from apps.core.documentos import respuesta_excel
from apps.core.filtros import Filtros
from apps.core.validadores import TIPOS_MIME
from apps.cuentas.permisos import denegar, permiso_requerido
from apps.estudiantes.acceso import estudiantes_visibles
from apps.estudiantes.forms import estudiantes_activos
from apps.estudiantes.models import GRUPO_ENSENANZA, TRAMO_CONVIVENCIA, Curso

from . import servicios
from .forms import (ActividadForm, AnotacionForm, CerrarProtocoloForm, ConflictoForm, EvidenciaForm, ProtocoloForm,
                    RegistroConductualForm)
from .models import ActividadPlan, Anotacion, Conflicto, EvidenciaActividad, ProtocoloActivado, RegistroConductual

POR_PAGINA = 20
NIVELES_CONFLICTO = [("basica", "Básica (1°–6°)"), ("media", "Media (7°–4°)")]
NIVELES_ENSENANZA = [("prebasica", "Prebásica"), ("basica", "Básica"), ("media", "Media")]


def _niveles_de(tramos, tabla):
    return [n for n, t in tabla.items() if t in tramos]


def _estudiante_inicial(request):
    if request.GET.get("estudiante", "").isdigit():
        return {"estudiante": int(request.GET["estudiante"])}
    return {}


# ---------------------------------------------------------------------------------------------- conflictos
@permiso_requerido("convivencia.ver")
def conflictos(request):
    f = Filtros(request, usar=("anio", "mes", "nivel"), niveles=NIVELES_CONFLICTO)
    base = f.filtrar_fecha(Conflicto.objects.select_related("curso", "encargada"), "fecha")
    por_tramo = {"basica": 0, "media": 0}
    for nivel in base.values_list("curso__nivel", flat=True):
        tramo = TRAMO_CONVIVENCIA.get(nivel)
        if tramo in por_tramo:
            por_tramo[tramo] += 1
    qs = base.filter(curso__nivel__in=_niveles_de({f.nivel}, TRAMO_CONVIVENCIA)) if f.nivel else base
    tipo = request.GET.get("tipo", "")
    if tipo == "mediacion":
        qs = qs.filter(tipo_gestion="mediacion")
    elif tipo == "otros":
        qs = qs.exclude(tipo_gestion="mediacion")
    total = base.count()
    qs = qs.annotate(n=Count("participantes")).order_by("-fecha", "-id")   # Meta.ordering no aplica con GROUP BY
    return render(request, "convivencia/conflictos.html", {
        **f.contexto(), "pagina": Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina")), "tipo": tipo,
        "total": total, "por_tramo": por_tramo,
        "pct_basica": round(100 * por_tramo["basica"] / (por_tramo["basica"] + por_tramo["media"]), 1)
        if por_tramo["basica"] + por_tramo["media"] else 50,
        "accion_barra": {"texto": "Registrar conflicto", "url": reverse("convivencia:conflicto_nuevo")}
        if request.user.tiene_permiso("convivencia.gestionar") else None})


@permiso_requerido("convivencia.gestionar")
def conflicto_form(request, pk=None):
    conflicto = get_object_or_404(Conflicto, pk=pk) if pk else None
    form = ConflictoForm(request.POST or None, instance=conflicto, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        registrar(request.user, "modificacion" if pk else "creacion", "conflicto", obj.pk)
        messages.success(request, "Conflicto guardado.")
        return redirect("convivencia:conflicto", obj.pk)
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "Editar conflicto" if pk else "Registrar conflicto",
        "volver_url": reverse("convivencia:conflictos"),
        "ayuda": "Gestión colaborativa del conflicto (mediación, negociación, arbitraje pedagógico) según el manual de "
                 "convivencia. La descripción y los acuerdos se guardan cifrados."})


@permiso_requerido("convivencia.ver")
def conflicto_detalle(request, pk):
    c = get_object_or_404(Conflicto.objects.select_related("curso", "encargada"), pk=pk)
    registrar(request.user, "consulta", "conflicto", c.pk)
    return render(request, "convivencia/conflicto_detalle.html", {
        "c": c, "participantes": c.participantes.select_related("curso")})


# ---------------------------------------------------------------------------------------------- anotaciones
def _anotaciones_visibles(usuario):
    if usuario.tiene_permiso("convivencia.ver"):
        return Anotacion.objects.all()
    return Anotacion.objects.filter(estudiante__in=estudiantes_visibles(usuario))


@permiso_requerido("convivencia.ver", "anotacion.registrar")
def anotaciones(request):
    f = Filtros(request, usar=("anio", "mes", "curso"))
    qs = f.filtrar_fecha(_anotaciones_visibles(request.user).filter(estudiante__curso__anio_escolar=f.anio), "fecha")
    if f.curso:
        qs = qs.filter(estudiante__curso=f.curso)
    conteo = dict(qs.values_list("tipo").annotate(n=Count("id")))
    total = sum(conteo.values())
    kpis = [{"clave": c, "etiqueta": e, "color": color, "valor": conteo.get(c, 0),
             "pct": round(100 * conteo.get(c, 0) / total) if total else 0} for c, e, color in servicios.COLORES_ANOTACION]
    ciclo = request.GET.get("ciclo", "")
    ciclo = ciclo if ciclo in dict(servicios.CICLOS) else ""
    filas = servicios.anotaciones_por_curso(qs, ciclo)
    return render(request, "convivencia/anotaciones.html", {
        **f.contexto(), "kpis": kpis, "total": total, "ciclo": ciclo, "ciclos": servicios.CICLOS, "filas": filas,
        "grafico": mark_safe(servicios.grafico_barras_apiladas(filas)), "colores": servicios.COLORES_ANOTACION,
        "recientes": qs.select_related("estudiante", "estudiante__curso", "registrada_por")[:15],
        "accion_barra": {"texto": "Registrar anotación", "url": reverse("convivencia:anotacion_nueva")}
        if request.user.tiene_permiso("anotacion.registrar") else None})


@permiso_requerido("anotacion.registrar")
def anotacion_nueva(request):
    u = request.user
    # El profesor jefe solo anota a estudiantes de su curso; convivencia, inspectoría y el equipo, a cualquiera.
    estudiantes = estudiantes_activos() if u.tiene_permiso("convivencia.ver") else \
        estudiantes_visibles(u).activos().select_related("curso")
    form = AnotacionForm(request.POST or None, estudiantes=estudiantes, usuario=u, initial=_estudiante_inicial(request))
    if request.method == "POST" and form.is_valid():
        a = form.save()
        registrar(u, "creacion", "anotacion", a.pk, detalle=a.tipo)
        messages.success(request, "Anotación registrada.")
        destino = request.GET.get("volver")
        return redirect("estudiantes:detalle", a.estudiante_id) if destino == "ficha" or "estudiante" in request.GET \
            else redirect("convivencia:anotaciones")
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "Registrar anotación", "volver_url": reverse("convivencia:anotaciones"),
        "ayuda": "Las faltas se clasifican como moderadas, graves o gravísimas según el reglamento interno."})


# ---------------------------------------------------------------------------------------------- situación conductual
CATEGORIAS = RegistroConductual.CATEGORIAS


def _registros(request, f):
    qs = f.filtrar_fecha(RegistroConductual.objects.filter(estudiante__curso__anio_escolar=f.anio), "fecha")
    return qs.filter(estudiante__curso=f.curso) if f.curso else qs


def _resumen_por_curso(qs):
    filas = {}
    for curso_id, categoria, n in qs.values_list("estudiante__curso", "categoria").annotate(n=Count("id")):
        filas.setdefault(curso_id, {c: 0 for c, _ in CATEGORIAS})[categoria] = n
    cursos = {c.pk: c for c in Curso.objects.filter(pk__in=filas).ordenados()}
    return [{"curso": cursos[pk], "valores": [v[c] for c, _ in CATEGORIAS], "total": sum(v.values())}
            for pk, v in sorted(filas.items(), key=lambda kv: (cursos[kv[0]].orden, cursos[kv[0]].letra))]


@permiso_requerido("convivencia.ver")
def situacion(request):
    f = Filtros(request, usar=("anio", "mes", "curso"))
    qs = _registros(request, f)
    conteo = dict(qs.values_list("categoria").annotate(n=Count("id")))
    return render(request, "convivencia/situacion.html", {
        **f.contexto(), "kpis": [(e, conteo.get(c, 0)) for c, e in CATEGORIAS], "filas": _resumen_por_curso(qs),
        "categorias": CATEGORIAS,
        "accion_barra": {"texto": "Nuevo registro", "url": reverse("convivencia:registro_nuevo")}
        if request.user.tiene_permiso("convivencia.gestionar") else None})


@permiso_requerido("convivencia.ver")
def situacion_detalle(request):
    f = Filtros(request, usar=("anio", "mes", "curso"))
    qs = _registros(request, f).select_related("estudiante", "estudiante__curso", "registrado_por")
    categoria = request.GET.get("categoria", "")
    if categoria in dict(CATEGORIAS):
        qs = qs.filter(categoria=categoria)
    registrar(request.user, "consulta", "registro_conductual", None, detalle="detalle %s" % (f.curso or f.anio))
    return render(request, "convivencia/situacion_detalle.html", {
        **f.contexto(), "pagina": Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina")),
        "categoria": categoria, "categorias": CATEGORIAS})


@permiso_requerido("convivencia.ver")
def situacion_descargar(request):
    f = Filtros(request, usar=("anio", "mes", "curso"))
    qs = _registros(request, f).select_related("estudiante", "estudiante__curso", "registrado_por")
    tipo = request.GET.get("tipo", "resumen")
    periodo = "%s%s" % (f.anio, "-%02d" % f.mes if f.mes else "")
    encabezado = ["Curso", "Estudiante", "RUT", "Fecha", "Categoría", "% asistencia", "Descripción", "Registrado por"]

    def fila(r):
        return [r.estudiante.curso.nombre, r.estudiante.nombre_lista, r.estudiante.rut_formateado, r.fecha,
                r.get_categoria_display(), float(r.porcentaje_asistencia) if r.porcentaje_asistencia is not None else "",
                r.descripcion, r.registrado_por.nombre_completo]

    if tipo == "detalle":
        hojas = [("Detalle %s" % periodo, encabezado, [fila(r) for r in qs])]
    elif tipo == "masiva":
        por_curso = {}
        for r in qs.order_by("estudiante__apellido_paterno", "fecha"):
            por_curso.setdefault(r.estudiante.curso, []).append(fila(r))
        hojas = [(c.nombre, encabezado, filas) for c, filas in
                 sorted(por_curso.items(), key=lambda kv: (kv[0].orden, kv[0].letra))] or [("Sin registros", encabezado, [])]
    else:
        tipo = "resumen"
        hojas = [("Resumen %s" % periodo, ["Curso"] + [e for _, e in CATEGORIAS] + ["Total"],
                  [[x["curso"].nombre] + x["valores"] + [x["total"]] for x in _resumen_por_curso(qs)])]
    registrar(request.user, "exportacion", "registro_conductual", None, detalle="Excel %s %s" % (tipo, periodo))
    return respuesta_excel("situacion_conductual_%s_%s.xlsx" % (tipo, periodo), hojas)


@permiso_requerido("convivencia.gestionar")
def registro_nuevo(request):
    form = RegistroConductualForm(request.POST or None, usuario=request.user, initial=_estudiante_inicial(request))
    if request.method == "POST" and form.is_valid():
        r = form.save()
        registrar(request.user, "creacion", "registro_conductual", r.pk, detalle=r.categoria)
        if r.categoria == "asistencia" and r.porcentaje_asistencia < 85:
            gravedad = "crítica" if r.porcentaje_asistencia < 50 else "grave"
            messages.warning(request, "Inasistencia %s (%s %%). Según el reglamento, Inspectoría deriva el caso a la "
                                      "Trabajadora Social en el marco del protocolo de vulneración de derechos."
                             % (gravedad, str(r.porcentaje_asistencia).replace(".", ",")))
        messages.success(request, "Registro guardado.")
        return redirect(reverse("convivencia:situacion_detalle") + "?curso=%d&anio=%d" % (r.estudiante.curso_id,
                                                                                           r.estudiante.curso.anio_escolar))
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "Nuevo registro de situación conductual", "volver_url": reverse("convivencia:situacion"),
        "ayuda": "Asistencia: el reglamento considera inasistencia reiterada entre 85 % y 89 %, grave entre 50 % y 84 % "
                 "y crítica bajo 50 %."})


# ---------------------------------------------------------------------------------------------- protocolos
@permiso_requerido("protocolo.ver", "protocolo.gestionar")
def protocolos(request):
    f = Filtros(request, usar=("anio", "nivel"), niveles=NIVELES_ENSENANZA)
    base = ProtocoloActivado.objects.filter(fecha_activacion__year=f.anio).select_related("curso", "responsable")
    por_nivel = {n: 0 for n, _ in NIVELES_ENSENANZA}
    for nivel in base.values_list("curso__nivel", flat=True):
        por_nivel[GRUPO_ENSENANZA.get(nivel, "basica")] += 1
    qs = base.filter(curso__nivel__in=_niveles_de({f.nivel}, GRUPO_ENSENANZA)) if f.nivel else base
    estado = request.GET.get("estado", "")
    if estado in ("abierto", "cerrado"):
        qs = qs.filter(estado=estado)
    total, cerrados = base.count(), base.filter(estado="cerrado").count()
    maximo = max(por_nivel.values()) or 1
    return render(request, "convivencia/protocolos.html", {
        **f.contexto(), "pagina": Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina")), "estado": estado,
        "total": total, "abiertos": total - cerrados, "cerrados": cerrados,
        "tasa": 100 * cerrados / total if total else None,
        "por_nivel": [{"nombre": n, "valor": por_nivel[c], "ancho": round(100 * por_nivel[c] / maximo, 1)}
                      for c, n in NIVELES_ENSENANZA],
        "accion_barra": {"texto": "Registrar protocolo", "url": reverse("convivencia:protocolo_nuevo")}
        if request.user.tiene_permiso("protocolo.gestionar") else None})


@permiso_requerido("protocolo.gestionar")
def protocolo_nuevo(request):
    form = ProtocoloForm(request.POST or None, usuario=request.user, initial=_estudiante_inicial(request))
    if request.method == "POST" and form.is_valid():
        p = form.save()
        registrar(request.user, "creacion", "protocolo_activado", p.pk, detalle=p.protocolo)
        messages.success(request, "Protocolo registrado como abierto.")
        return redirect("convivencia:protocolo", p.pk)
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "Registrar protocolo", "volver_url": reverse("convivencia:protocolos"),
        "ayuda": "Protocolos de actuación del reglamento interno. Si la situación afecta a un estudiante en riesgo, "
                 "registre también la alerta de riesgo: tiene plazos legales y notifica a los responsables."})


@permiso_requerido("protocolo.ver", "protocolo.gestionar")
def protocolo_detalle(request, pk):
    p = get_object_or_404(ProtocoloActivado.objects.select_related("curso", "estudiante", "responsable", "alerta"), pk=pk)
    registrar(request.user, "consulta", "protocolo_activado", p.pk)
    gestiona = request.user.tiene_permiso("protocolo.gestionar") and p.estado == "abierto"
    form = CerrarProtocoloForm(request.POST or None, protocolo=p) if gestiona else None
    if request.method == "POST":
        if not gestiona:
            denegar(request, "cierre protocolo %d" % pk)
        if form.is_valid():
            p.estado, p.fecha_cierre = "cerrado", form.cleaned_data["fecha_cierre"]
            p.observaciones = form.cleaned_data["observaciones"]
            p.full_clean()
            p.save()
            registrar(request.user, "modificacion", "protocolo_activado", p.pk, detalle="cierre")
            messages.success(request, "Protocolo cerrado.")
            return redirect("convivencia:protocolo", p.pk)
    return render(request, "convivencia/protocolo_detalle.html", {"p": p, "form": form, "nivel": servicios.nivel_de(p.curso)})


# ---------------------------------------------------------------------------------------------- plan de gestión
@permiso_requerido("plan_convivencia.ver", "plan_convivencia.gestionar")
def plan(request):
    f = Filtros(request, usar=("anio", "mes"))
    base = f.filtrar_fecha(ActividadPlan.objects.select_related("responsable").annotate(n_evidencias=Count("evidencias")),
                           "fecha")
    estado = request.GET.get("estado", "")
    qs = base.filter(estado=estado) if estado in ("realizada", "pendiente") else base
    qs = qs.order_by("-fecha", "-id")
    return render(request, "convivencia/plan.html", {
        **f.contexto(), "pagina": Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina")), "estado": estado,
        "conteo": {"todas": base.count(), "realizada": base.filter(estado="realizada").count(),
                   "pendiente": base.filter(estado="pendiente").count()},
        "accion_barra": {"texto": "Registrar actividad", "url": reverse("convivencia:actividad_nueva")}
        if request.user.tiene_permiso("plan_convivencia.gestionar") else None})


@permiso_requerido("plan_convivencia.ver", "plan_convivencia.gestionar")
def plan_descargar(request):
    f = Filtros(request, usar=("anio", "mes"))
    qs = f.filtrar_fecha(ActividadPlan.objects.select_related("responsable").annotate(n=Count("evidencias")), "fecha")
    qs = qs.order_by("fecha", "id")
    filas = [[a.get_tipo_display(), a.titulo, a.fecha, a.responsable.nombre_completo, a.medio_verificacion,
              a.get_estado_display(), a.n, a.descripcion] for a in qs.order_by("fecha")]
    registrar(request.user, "exportacion", "actividad_plan", None, detalle="Excel %s" % f.anio)
    return respuesta_excel("plan_de_gestion_%s.xlsx" % f.anio, [(
        "Plan de gestión %s" % f.anio,
        ["Tipo", "Título", "Fecha", "Responsable", "Medio de verificación", "Estado", "Evidencias", "Descripción"], filas)])


@permiso_requerido("plan_convivencia.gestionar")
def actividad_form(request, pk=None):
    actividad = get_object_or_404(ActividadPlan, pk=pk) if pk else None
    form = ActividadForm(request.POST or None, instance=actividad, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        registrar(request.user, "modificacion" if pk else "creacion", "actividad_plan", obj.pk)
        messages.success(request, "Actividad guardada.")
        return redirect("convivencia:actividad", obj.pk)
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "Editar actividad" if pk else "Registrar actividad",
        "volver_url": reverse("convivencia:plan"),
        "ayuda": "Actividades del plan de gestión de convivencia escolar. Una actividad realizada debe indicar su medio "
                 "de verificación; las evidencias se adjuntan en la actividad."})


@permiso_requerido("plan_convivencia.ver", "plan_convivencia.gestionar")
def actividad_detalle(request, pk):
    a = get_object_or_404(ActividadPlan.objects.select_related("responsable"), pk=pk)
    gestiona = request.user.tiene_permiso("plan_convivencia.gestionar")
    form = EvidenciaForm(request.POST or None, request.FILES or None) if gestiona else None
    if request.method == "POST":
        if not gestiona:
            denegar(request, "evidencia actividad %d" % pk)
        if form.is_valid():
            with transaction.atomic():
                servicios.guardar_evidencia(form.cleaned_data["archivo"], a, request.user)
            messages.success(request, "Evidencia adjuntada y cifrada.")
            return redirect("convivencia:actividad", a.pk)
    return render(request, "convivencia/actividad_detalle.html", {
        "a": a, "evidencias": a.evidencias.select_related("subida_por"), "form": form, "gestiona": gestiona})


@permiso_requerido("plan_convivencia.ver", "plan_convivencia.gestionar")
def evidencia_descargar(request, pk):
    ev = get_object_or_404(EvidenciaActividad, pk=pk)
    try:
        datos = servicios.leer_evidencia(ev)
    except Exception:
        registrar(request.user, "acceso_denegado", "evidencia_actividad", ev.pk, detalle="integridad o cifrado inválido")
        messages.error(request, "No se pudo abrir la evidencia: su integridad no pudo verificarse.")
        return redirect("convivencia:actividad", ev.actividad_id)
    registrar(request.user, "exportacion", "evidencia_actividad", ev.pk)
    extension = "." + ev.nombre_archivo.rsplit(".", 1)[-1].lower() if "." in ev.nombre_archivo else ""
    respuesta = HttpResponse(datos, content_type=TIPOS_MIME.get(extension, "application/octet-stream"))
    respuesta["Content-Disposition"] = 'attachment; filename="%s"' % ev.nombre_archivo.replace('"', "")
    return respuesta


# ---------------------------------------------------------------------------------------------- indicadores
@permiso_requerido("reportes.ver")
def indicadores(request):
    f = Filtros(request, usar=("anio",))
    datos = servicios.indicadores_bienestar(f.anio)
    registrar(request.user, "consulta", "reportes", None, detalle="indicadores de bienestar %s" % f.anio)
    from apps.core.filtros import MESES
    return render(request, "convivencia/indicadores.html", {**f.contexto(), "d": datos,
                                                            "nombre_mes": MESES[datos["mes"] - 1]})
