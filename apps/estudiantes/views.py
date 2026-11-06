"""Pantallas «Estudiantes» del prototipo v1: lista, registrar, cursos, promoción y egresados; más la ficha, la
importación y exportación en Excel y los PDF de fichas y nóminas."""
import datetime

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.auditoria.servicios import registrar
from apps.casos.acceso import casos_visibles
from apps.casos.models import Hito
from apps.core.documentos import leer_excel, respuesta_excel
from apps.core.filtros import Filtros
from apps.cuentas.permisos import denegar, permiso_requerido

from . import servicios
from .acceso import es_profesor_jefe_de, estudiantes_visibles
from .forms import (COLUMNAS_IMPORTACION, ApoderadoForm, ApoderadoRapidoForm, CursoForm, EstudianteForm, ImportarForm,
                    MarcarInactivoForm, VincularApoderadoForm, validar_importacion)
from .models import GRUPO_ENSENANZA, Apoderado, Curso, Estudiante, EstudianteApoderado, ProcesoPromocion

POR_PAGINA = 25


def _estudiante_visible(request, pk):
    estudiante = get_object_or_404(Estudiante.objects.select_related("curso", "curso__sede", "curso__profesor_jefe"), pk=pk)
    if not estudiantes_visibles(request.user).filter(pk=pk).exists():
        denegar(request, "ficha de estudiante %d" % pk)
    return estudiante


def _lista_filtrada(request, f):
    qs = servicios.matriculados(estudiantes_visibles(request.user), f.anio).select_related("curso", "curso__sede")
    if f.curso:
        qs = qs.filter(curso=f.curso)
    if f.programa == "pie":
        qs = qs.filter(en_pie=True)
    elif f.programa == "prioritario":
        qs = qs.filter(prioritario=True)
    elif f.programa == "ninguno":
        qs = qs.filter(en_pie=False, prioritario=False)
    return qs


# ---------------------------------------------------------------------------------------------- lista
@permiso_requerido("estudiante.ver_todos", "estudiante.ver_curso")
def lista(request):
    f = Filtros(request, usar=("anio", "programa", "curso"))
    base = _lista_filtrada(request, f)
    q = " ".join(request.GET.get("q", "").split())
    if q and request.GET.get("ir") == "1":
        # Buscador global de la barra superior: si hay una sola coincidencia (de cualquier año), va directo a la ficha.
        coincidencias = estudiantes_visibles(request.user).buscar(q)
        if coincidencias.count() == 1:
            return redirect("estudiantes:detalle", coincidencias.get().pk)
    estado = request.GET.get("estado", "todos")
    conteo = {"todos": base.count(), "activos": base.activos().count(), "inactivos": base.inactivos().count()}
    qs = base.activos() if estado == "activos" else base.inactivos() if estado == "inactivos" else base
    if q:
        qs = qs.buscar(q)
    qs = qs.order_by("apellido_paterno", "apellido_materno", "primer_nombre")
    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina"))
    return render(request, "estudiantes/lista.html", {
        **f.contexto(), "pagina": pagina, "q": q, "estado": estado, "conteo": conteo,
        "kpi": servicios.indicadores(estudiantes_visibles(request.user), f.anio),
        "inicio": pagina.start_index(),
        "accion_barra": {"texto": "Agregar estudiante", "url": reverse("estudiantes:crear")}
        if request.user.tiene_permiso("estudiante.gestionar") else None})


@permiso_requerido("estudiante.importar")
def exportar(request):
    f = Filtros(request, usar=("anio", "programa", "curso"))
    qs = _lista_filtrada(request, f)
    ids = [int(i) for i in request.GET.getlist("ids") if i.isdigit()]
    if ids:
        qs = qs.filter(pk__in=ids)
    estado = request.GET.get("estado")
    qs = qs.activos() if estado == "activos" else qs.inactivos() if estado == "inactivos" else qs
    qs = qs.order_by("curso__nivel", "apellido_paterno", "apellido_materno")
    filas = []
    for e in qs.prefetch_related("vinculos_apoderado__apoderado"):
        titular = next((v.apoderado for v in e.vinculos_apoderado.all() if v.es_titular), None)
        filas.append([e.rut_formateado, e.primer_nombre, e.segundo_nombre, e.apellido_paterno, e.apellido_materno,
                      e.nombre_social, e.fecha_nacimiento, e.curso.nombre, e.fecha_ingreso, e.en_pie,
                      e.get_necesidad_educativa_display() if e.necesidad_educativa != "ninguna" else "",
                      e.prioritario, e.get_estado_display(), titular.nombre_completo if titular else "",
                      titular.telefono if titular else "", titular.correo if titular else ""])
    registrar(request.user, "exportacion", "estudiante", None, detalle="nómina Excel %s: %d registros" % (f.anio, len(filas)))
    encabezados = [r.replace(" *", "") for _, r in COLUMNAS_IMPORTACION]
    encabezados.insert(12, "Estado")
    return respuesta_excel("estudiantes_%s.xlsx" % f.anio, [("Estudiantes %s" % f.anio, encabezados, filas)])


@permiso_requerido("estudiante.importar")
def plantilla(request):
    anio = timezone.localdate().year
    cursos = Curso.objects.filter(anio_escolar=anio).ordenados()
    ejemplo = ["12.345.678-5", "Nombre", "", "Apellido", "Apellido", "", "10-03-2016",
               cursos[0].nombre if cursos else "5° Básico A", "01-03-2026", "No", "", "No",
               "Nombre Apellido", "+56 9 1234 5678", "apoderado@correo.cl"]
    return respuesta_excel("plantilla_estudiantes.xlsx", [
        ("Estudiantes", [r for _, r in COLUMNAS_IMPORTACION], [ejemplo]),
        ("Cursos válidos %s" % anio, ["Curso", "Sede"], [[c.nombre, c.sede.nombre] for c in cursos]),
        ("Instrucciones", ["Columna", "Cómo completarla"], [
            ["RUT", "Con o sin puntos, con guion y dígito verificador. Se valida el dígito."],
            ["Fechas", "dd-mm-aaaa (por ejemplo 10-03-2016) o formato de fecha de Excel."],
            ["Curso", "Exactamente como en la hoja «Cursos válidos» (por ejemplo «5° Básico A»)."],
            ["PIE / Prioritario", "«Sí» o «No». Un estudiante PIE debe indicar NEE transitoria o permanente."],
            ["Apoderado", "Opcional. Si lo completa, indique nombre y apellido y al menos un teléfono o correo."],
            ["Fila de ejemplo", "Bórrela antes de importar: sus datos son ficticios."]])])


@permiso_requerido("estudiante.importar")
def importar(request):
    form = ImportarForm(request.POST or None, request.FILES or None)
    errores, anio = [], timezone.localdate().year
    if request.method == "POST" and form.is_valid():
        try:
            encabezados, filas = leer_excel(form.cleaned_data["archivo"])
        except Exception:
            form.add_error("archivo", "No se pudo leer la planilla. Use la plantilla descargada desde esta página.")
            filas, encabezados = [], []
        from apps.core.documentos import normalizar_encabezado
        faltan = [r for c, r in COLUMNAS_IMPORTACION if r.endswith("*") and normalizar_encabezado(r) not in encabezados]
        if form.is_valid() and faltan:
            form.add_error("archivo", "Faltan columnas obligatorias: %s." % ", ".join(r.replace(" *", "") for r in faltan))
        elif form.is_valid() and not filas:
            form.add_error("archivo", "La planilla no tiene filas con datos.")
        elif form.is_valid():
            listos, errores = validar_importacion(filas, anio)
            if not errores:
                with transaction.atomic():
                    for e, apoderado in listos:
                        e.save()
                        if apoderado is not None:
                            apoderado.save()
                            EstudianteApoderado.objects.create(estudiante=e, apoderado=apoderado, parentesco="otro",
                                                               es_titular=True)
                    registrar(request.user, "creacion", "estudiante", None,
                              detalle="importación Excel: %d estudiantes" % len(listos))
                messages.success(request, "Se importaron %d estudiantes." % len(listos))
                return redirect("estudiantes:lista")
    return render(request, "estudiantes/importar.html", {"form": form, "errores": errores, "anio": anio,
                                                         "columnas": COLUMNAS_IMPORTACION})


# ---------------------------------------------------------------------------------------------- ficha
@permiso_requerido("estudiante.ver_todos", "estudiante.ver_curso")
def detalle(request, pk):
    e = _estudiante_visible(request, pk)
    u = request.user
    registrar(u, "consulta", "estudiante", e.pk)
    ctx = {"e": e, "vinculos": e.vinculos_apoderado.select_related("apoderado"), "programas": servicios.programas(e)}
    ctx["casos"] = casos_visibles(u).filter(estudiante=e).select_related("responsable")
    ctx["planes"], ctx["ve_detalle_plan"] = None, False
    if u.tiene_permiso("plan.ver"):
        ctx["planes"], ctx["ve_detalle_plan"] = e.planes.all(), True
    elif u.tiene_permiso("plan.ver_adecuaciones") and es_profesor_jefe_de(u, e):
        ctx["planes"] = e.planes.filter(estado="vigente")
    if es_profesor_jefe_de(u, e) or u.tiene_permiso("caso.ver_equipo"):
        # E15: el profesor jefe ve observaciones, entrevistas al apoderado e hitos marcados como visibles.
        ctx["hitos_visibles"] = Hito.objects.filter(caso__estudiante=e, visible_profesor_jefe=True).order_by("-fecha")[:20]
    if u.tiene_permiso("consentimiento.gestionar"):
        ctx["consentimientos"] = e.consentimientos.select_related("apoderado")
    if u.tiene_permiso("convivencia.ver", "anotacion.registrar"):
        ctx["anotaciones"] = e.anotaciones.select_related("registrada_por")[:10]
        ctx["resumen_anotaciones"] = dict(e.anotaciones.values_list("tipo").annotate(n=Count("id")))
    if u.tiene_permiso("convivencia.ver"):
        ctx["registros"] = e.registros_conductuales.all()[:10]
    return render(request, "estudiantes/detalle.html", ctx)


@permiso_requerido("estudiante.ver_todos", "estudiante.ver_curso")
def ficha_pdf(request, pk):
    e = _estudiante_visible(request, pk)
    registrar(request.user, "exportacion", "estudiante", e.pk, detalle="ficha PDF")
    return servicios.ficha_pdf(e).respuesta("ficha_%s.pdf" % e.rut)


def _formulario_estudiante(request, instancia=None):
    form = EstudianteForm(request.POST or None, instance=instancia)
    form_apo = ApoderadoRapidoForm(request.POST or None) if instancia is None else None
    if request.method == "POST" and form.is_valid() and (form_apo is None or form_apo.is_valid()):
        with transaction.atomic():
            e = form.save()
            if form_apo is not None:
                vinculo = form_apo.guardar(e)
                if vinculo:
                    registrar(request.user, "creacion", "estudiante_apoderado", vinculo.pk)
            registrar(request.user, "modificacion" if instancia else "creacion", "estudiante", e.pk)
        messages.success(request, "Ficha actualizada." if instancia else "Estudiante registrado.")
        return redirect("estudiantes:detalle", e.pk)
    return render(request, "estudiantes/formulario.html", {
        "form": form, "form_apo": form_apo, "e": instancia,
        "volver_url": reverse("estudiantes:detalle", args=[instancia.pk]) if instancia else reverse("estudiantes:lista")})


@permiso_requerido("estudiante.gestionar")
def crear(request):
    return _formulario_estudiante(request)


@permiso_requerido("estudiante.gestionar")
def editar(request, pk):
    return _formulario_estudiante(request, _estudiante_visible(request, pk))


@permiso_requerido("estudiante.gestionar")
def marcar_inactivo(request, pk):
    e = _estudiante_visible(request, pk)
    if not e.activo:
        messages.info(request, "El estudiante ya no está activo.")
        return redirect("estudiantes:detalle", e.pk)
    form = MarcarInactivoForm(request.POST or None, estudiante=e)
    if request.method == "POST" and form.is_valid():
        e.fecha_egreso, e.tipo_salida = form.cleaned_data["fecha_retiro"], "retiro"
        e.full_clean()
        e.save(update_fields=["fecha_egreso", "tipo_salida"])
        registrar(request.user, "modificacion", "estudiante", e.pk, detalle="retiro")
        messages.success(request, "%s quedó como inactivo (retirado)." % e)
        return redirect("estudiantes:detalle", e.pk)
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "Marcar como inactivo — %s" % e, "boton": "Marcar como inactivo",
        "volver_url": reverse("estudiantes:detalle", args=[e.pk]),
        "advertencia": "El estudiante dejará de aparecer entre los activos y no podrá recibir nuevas atenciones, "
                       "anotaciones ni registros."})


@require_POST
@permiso_requerido("estudiante.gestionar")
def reactivar(request, pk):
    e = _estudiante_visible(request, pk)
    if e.tipo_salida == "retiro":
        e.fecha_egreso, e.tipo_salida = None, ""
        e.save(update_fields=["fecha_egreso", "tipo_salida"])
        registrar(request.user, "modificacion", "estudiante", e.pk, detalle="reactivación")
        messages.success(request, "Estudiante reactivado.")
    return redirect("estudiantes:detalle", e.pk)


@permiso_requerido("estudiante.gestionar")
def vincular_apoderado(request, pk):
    e = _estudiante_visible(request, pk)
    form = VincularApoderadoForm(request.POST or None, estudiante=e)
    if request.method == "POST" and form.is_valid():
        vinculo = form.save()
        registrar(request.user, "creacion", "estudiante_apoderado", vinculo.pk)
        messages.success(request, "Apoderado vinculado.")
        return redirect("estudiantes:detalle", e.pk)
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "Vincular apoderado a %s" % e, "volver_url": reverse("estudiantes:detalle", args=[e.pk]),
        "ayuda": "Si el RUT ya está registrado se usará ese apoderado; si no, se creará con los datos ingresados."})


@require_POST
@permiso_requerido("estudiante.gestionar")
def desvincular_apoderado(request, pk):
    vinculo = get_object_or_404(EstudianteApoderado, pk=pk)
    _estudiante_visible(request, vinculo.estudiante_id)
    if vinculo.apoderado.consentimientos.filter(estudiante=vinculo.estudiante).exists():
        messages.error(request, "No se puede desvincular: el apoderado otorgó consentimientos sobre este estudiante.")
    else:
        registrar(request.user, "eliminacion", "estudiante_apoderado", vinculo.pk)
        vinculo.delete()
        messages.success(request, "Apoderado desvinculado.")
    return redirect("estudiantes:detalle", vinculo.estudiante_id)


@permiso_requerido("estudiante.gestionar")
def editar_apoderado(request, pk):
    apoderado = get_object_or_404(Apoderado, pk=pk)
    vinculo = apoderado.vinculos_estudiante.first()
    if vinculo:
        _estudiante_visible(request, vinculo.estudiante_id)
    form = ApoderadoForm(request.POST or None, instance=apoderado)
    if request.method == "POST" and form.is_valid():
        form.save()
        registrar(request.user, "modificacion", "apoderado", apoderado.pk)
        messages.success(request, "Datos del apoderado actualizados.")
        return redirect("estudiantes:detalle", vinculo.estudiante_id) if vinculo else redirect("estudiantes:lista")
    return render(request, "comun/formulario.html", {"form": form, "titulo": "Datos de %s" % apoderado,
                                                     "volver_url": reverse("estudiantes:lista")})


# ---------------------------------------------------------------------------------------------- cursos
@permiso_requerido("estudiante.ver_todos", "curso.gestionar")
def cursos(request):
    f = Filtros(request, usar=("anio",))
    lista_cursos = list(Curso.objects.filter(anio_escolar=f.anio).ordenados().select_related("sede", "profesor_jefe")
                        .annotate(n=Count("estudiantes", filter=~Q(estudiantes__tipo_salida="egreso"))))
    grupos = []
    for clave, nombre in (("prebasica", "Prebásica"), ("basica", "Básica"), ("media", "Media")):
        del_grupo = [c for c in lista_cursos if GRUPO_ENSENANZA.get(c.nivel) == clave]
        if del_grupo:
            grupos.append({"nombre": nombre, "cursos": del_grupo})
    base = servicios.matriculados(Estudiante.objects.all(), f.anio)
    return render(request, "estudiantes/cursos.html", {
        **f.contexto(), "grupos": grupos, "total_cursos": len(lista_cursos),
        "kpi": {"estudiantes": base.count(), "activos": base.activos().count(),
                "rango": servicios.indicadores(Estudiante.objects.none(), f.anio)["rango_cursos"],
                "por_grupo": {g["nombre"]: len(g["cursos"]) for g in grupos}},
        "accion_barra": {"texto": "Crear curso", "url": reverse("estudiantes:curso_crear")}
        if request.user.tiene_permiso("curso.gestionar") else None})


@permiso_requerido("estudiante.ver_todos", "curso.gestionar")
def curso_detalle(request, pk):
    curso = get_object_or_404(Curso.objects.select_related("sede", "profesor_jefe"), pk=pk)
    estudiantes = curso.estudiantes.exclude(tipo_salida="egreso").order_by("apellido_paterno", "apellido_materno",
                                                                            "primer_nombre")
    registrar(request.user, "consulta", "curso", curso.pk)
    return render(request, "estudiantes/curso_detalle.html", {
        "curso": curso, "estudiantes": estudiantes,
        "activos": sum(1 for e in estudiantes if e.activo), "pie": sum(1 for e in estudiantes if e.en_pie),
        "prioritarios": sum(1 for e in estudiantes if e.prioritario)})


@permiso_requerido("estudiante.ver_todos", "curso.gestionar")
def cursos_pdf(request, pk=None):
    ids = [pk] if pk else [int(i) for i in request.GET.getlist("ids") if i.isdigit()]
    seleccion = list(Curso.objects.filter(pk__in=ids).ordenados().select_related("sede", "profesor_jefe"))
    if not seleccion:
        messages.error(request, "Seleccione al menos un curso para descargar.")
        return redirect(reverse("estudiantes:cursos") + ("?anio=%s" % request.GET["anio"] if request.GET.get("anio") else ""))
    registrar(request.user, "exportacion", "curso", seleccion[0].pk if len(seleccion) == 1 else None,
              detalle="nómina PDF: %s" % ", ".join(c.nombre for c in seleccion))
    nombre = "nomina_%s_%s.pdf" % (seleccion[0].abreviatura.replace("°", ""), seleccion[0].letra) \
        if len(seleccion) == 1 else "nominas_%d_cursos.pdf" % len(seleccion)
    return servicios.nomina_pdf(seleccion).respuesta(nombre)


@permiso_requerido("curso.gestionar")
def curso_form(request, pk=None):
    curso = get_object_or_404(Curso, pk=pk) if pk else None
    form = CursoForm(request.POST or None, instance=curso)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        registrar(request.user, "modificacion" if pk else "creacion", "curso", obj.pk)
        messages.success(request, "Curso guardado.")
        return redirect("estudiantes:curso", obj.pk)
    return render(request, "comun/formulario.html", {"form": form, "titulo": "Editar curso" if pk else "Crear curso",
                                                     "volver_url": reverse("estudiantes:cursos")})


# ---------------------------------------------------------------------------------------------- promoción
def _contexto_promocion(request, paso):
    f = Filtros(request, usar=("anio",))
    proceso = servicios.proceso_del_anio(f.anio)
    return f, proceso, {**f.contexto(), "proceso": proceso, "paso": paso,
                        "habilitado": servicios.puede_procesar(proceso),
                        "fecha_habilita": datetime.date(proceso.anio, *servicios.FECHA_HABILITA_PROCESO)}


@permiso_requerido("promocion.gestionar")
def promocion(request):
    f, proceso, ctx = _contexto_promocion(request, 1)
    cursos_anio = list(Curso.objects.filter(anio_escolar=f.anio).ordenados())
    if request.method == "POST" and not proceso.procesado:
        ids = {int(i) for i in request.POST.getlist("terminales") if i.isdigit()}
        terminales = [c for c in cursos_anio if c.pk in ids]
        try:
            servicios.validar_terminales(cursos_anio, terminales)
        except ValidationError as e:
            for m in e.messages:
                messages.error(request, m)
        else:
            proceso.cursos_terminales.set(terminales)
            proceso.estado = "borrador"
            proceso.save(update_fields=["estado"])
            registrar(request.user, "modificacion", "proceso_promocion", proceso.pk,
                      detalle="cursos terminales: %s" % ", ".join(c.nombre for c in terminales))
            if request.POST.get("accion") == "continuar":
                return redirect(reverse("estudiantes:promocion_revisar") + f.url())
            messages.success(request, "Borrador guardado.")
            return redirect(reverse("estudiantes:promocion") + f.url())
    elegidos = set(proceso.cursos_terminales.values_list("pk", flat=True))
    if not elegidos and not proceso.procesado:
        elegidos = {c.pk for c in cursos_anio if c.nivel == "4M"}       # sugerencia para colegios completos
    return render(request, "estudiantes/promocion.html", {**ctx, "cursos": cursos_anio, "elegidos": elegidos})


@permiso_requerido("promocion.gestionar")
def promocion_revisar(request):
    f, proceso, ctx = _contexto_promocion(request, 2)
    if not proceso.cursos_terminales.exists():
        messages.error(request, "Primero defina los cursos terminales (paso 1).")
        return redirect(reverse("estudiantes:promocion") + f.url())
    if request.method == "POST" and not proceso.procesado:
        repitentes = {int(i) for i in request.POST.getlist("repite") if i.isdigit()}
        servicios.guardar_revision(proceso, repitentes, request.user)
        if request.POST.get("accion") == "continuar":
            return redirect(reverse("estudiantes:promocion_procesar") + f.url())
        messages.success(request, "Revisión guardada.")
        return redirect(reverse("estudiantes:promocion_revisar") + f.url())
    terminales = set(proceso.cursos_terminales.values_list("pk", flat=True))
    marcados = set(proceso.resultados.filter(resultado="repite").values_list("estudiante_id", flat=True))
    por_curso = {}
    for e in servicios.estudiantes_a_promover(proceso):
        por_curso.setdefault(e.curso, []).append(e)
    grupos = [{"curso": c, "estudiantes": ests, "terminal": c.pk in terminales}
              for c, ests in sorted(por_curso.items(), key=lambda kv: (kv[0].orden, kv[0].letra))]
    return render(request, "estudiantes/promocion_revisar.html", {**ctx, "grupos": grupos, "marcados": marcados})


@permiso_requerido("promocion.gestionar")
def promocion_procesar(request):
    f, proceso, ctx = _contexto_promocion(request, 3)
    if proceso.estado == "borrador":
        messages.error(request, "Primero revise la promoción (paso 2).")
        return redirect(reverse("estudiantes:promocion_revisar") + f.url())
    if request.method == "POST":
        try:
            creados = servicios.procesar(proceso, request.user)
        except ValidationError as e:
            for m in e.messages:
                messages.error(request, m)
        else:
            messages.success(request, "Fin de año %s procesado. Se crearon %d cursos para %s." % (
                proceso.anio, creados, proceso.anio + 1))
            return redirect(reverse("estudiantes:egresados") + "?anio=%s" % proceso.anio)
    return render(request, "estudiantes/promocion_procesar.html", {
        **ctx, "filas": servicios.resumen_destinos(proceso), "siguiente": proceso.anio + 1,
        "totales": dict(proceso.resultados.values_list("resultado").annotate(n=Count("id")))})


# ---------------------------------------------------------------------------------------------- egresados
@permiso_requerido("estudiante.ver_todos")
def egresados(request):
    hoy = timezone.localdate()
    todos = Estudiante.objects.egresados().select_related("curso")
    anios = sorted({f.year for f in todos.values_list("fecha_egreso", flat=True)}, reverse=True)
    anio = request.GET.get("anio", "")
    anio = int(anio) if anio.isdigit() and int(anio) in anios else None
    qs = todos.filter(fecha_egreso__year=anio) if anio else todos
    qs = qs.order_by("-fecha_egreso", "apellido_paterno", "apellido_materno")
    menus = [{"etiqueta": "Año de egreso: %s" % (anio or "Todos"), "opciones": [
        {"texto": "Todos", "url": "?", "activo": anio is None}] + [
        {"texto": str(a), "url": "?anio=%s" % a, "activo": a == anio} for a in anios]}]
    ultimo = ProcesoPromocion.objects.filter(estado="procesado").order_by("-anio").first()
    actual = ProcesoPromocion.objects.filter(anio=hoy.year).first()
    return render(request, "estudiantes/egresados.html", {
        "filtros_barra": menus, "pagina": Paginator(qs, POR_PAGINA).get_page(request.GET.get("pagina")),
        "total": todos.count(), "ultimo": ultimo, "anio_actual": hoy.year,
        "terminales_actuales": list(actual.cursos_terminales.ordenados()) if actual else [],
        "ultimo_anio_egreso": todos.aggregate(m=Max("fecha_egreso"))["m"]})
