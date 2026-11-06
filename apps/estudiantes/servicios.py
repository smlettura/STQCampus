"""Indicadores de la lista de estudiantes, fichas y nóminas en PDF, y promoción de fin de año."""
import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.auditoria.servicios import registrar
from apps.core.documentos import DocumentoPDF

from .models import NIVELES, Curso, Estudiante, ProcesoPromocion, PromocionEstudiante


# ---------------------------------------------------------------------------------------------- lista e indicadores
def matriculados(qs, anio):
    """Estudiantes de los cursos del año (activos y retirados); los egresados se ven en «Egresados»."""
    return qs.filter(curso__anio_escolar=anio).exclude(tipo_salida="egreso")


def indicadores(qs, anio):
    base = matriculados(qs, anio)
    total = base.count()
    inactivos = base.inactivos().count()
    repitentes = PromocionEstudiante.objects.filter(proceso__anio=anio - 1, resultado="repite",
                                                    estudiante__in=base).count()
    cursos = Curso.objects.filter(anio_escolar=anio).ordenados()
    niveles = [c.nivel for c in cursos]
    rango = ""
    if niveles:
        nombres = dict(NIVELES)
        rango = "%s a %s" % (nombres[niveles[0]], nombres[niveles[-1]]) if len(set(niveles)) > 1 else nombres[niveles[0]]
    return {
        "total": total, "activos": total - inactivos, "inactivos": inactivos,
        "pct_activos": 100 * (total - inactivos) / total if total else None,
        "tasa_retiro": 100 * inactivos / total if total else None,
        "repitentes": repitentes, "tasa_repitencia": 100 * repitentes / total if total else None,
        "cursos": len(niveles), "rango_cursos": rango,
    }


def programas(e):
    return [p for p, activo in (("PIE", e.en_pie), ("PRIORITARIO", e.prioritario)) if activo]


# ---------------------------------------------------------------------------------------------- PDF
def _fecha(f):
    return f.strftime("%d/%m/%Y") if f else "—"


def ficha_pdf(e):
    """Ficha administrativa del estudiante. No incluye contenido clínico (notas, diagnósticos ni alertas)."""
    pdf = DocumentoPDF("Ficha del estudiante", "%s · %s · RUT %s" % (e.nombre_completo, e.curso.nombre, e.rut_formateado))
    pdf.seccion("Información personal")
    pdf.datos([("RUT", e.rut_formateado), ("Fecha de nacimiento", "%s (%s años)" % (_fecha(e.fecha_nacimiento), e.edad)),
               ("Primer nombre", e.primer_nombre), ("Segundo nombre", e.segundo_nombre or "—"),
               ("Apellido paterno", e.apellido_paterno), ("Apellido materno", e.apellido_materno),
               ("Nombre social", e.nombre_social or "—"), ("Estado", e.get_estado_display())])
    pdf.seccion("Datos académicos")
    pdf.datos([("Curso", "%s %s" % (e.curso.nombre, e.curso.anio_escolar)), ("Sede", e.curso.sede.nombre),
               ("Profesor jefe", e.curso.profesor_jefe.nombre_completo if e.curso.profesor_jefe else "—"),
               ("Fecha de ingreso", _fecha(e.fecha_ingreso)),
               ("Programas", ", ".join(programas(e)) or "Sin programas"),
               ("Necesidad educativa", e.get_necesidad_educativa_display()),
               ("Matrícula condicional", "Sí" if e.matricula_condicional else "No"),
               ("Salida", "%s el %s" % (e.get_tipo_salida_display(), _fecha(e.fecha_egreso)) if e.fecha_egreso else "—")])
    pdf.seccion("Apoderados")
    pdf.tabla(["Nombre", "Parentesco", "Teléfono", "Correo", "Titular"],
              [[v.apoderado.nombre_completo, v.get_parentesco_display(), v.apoderado.telefono or "—",
                v.apoderado.correo or "—", "Sí" if v.es_titular else "No"]
               for v in e.vinculos_apoderado.select_related("apoderado")],
              anchos=[150, 70, 95, 165, 60], vacio="Sin apoderados registrados.")
    pdf.parrafo("Esta ficha no incluye información del acompañamiento psicosocial, que es reservada del equipo.")
    return pdf


def _encabezado_nomina(curso):
    n = curso.estudiantes.exclude(tipo_salida="egreso").count()
    return ("Nómina %s" % curso.nombre, "Año escolar %s · Sede %s · Profesor jefe: %s · %d estudiantes" % (
        curso.anio_escolar, curso.sede.nombre,
        curso.profesor_jefe.nombre_completo if curso.profesor_jefe else "sin asignar", n))


def _tabla_nomina(pdf, curso):
    estudiantes = curso.estudiantes.exclude(tipo_salida="egreso").order_by("apellido_paterno", "apellido_materno",
                                                                            "primer_nombre")
    pdf.tabla(["N°", "Estudiante", "RUT", "Programas", "Estado"],
              [[i, "%s%s" % (e.nombre_lista, " (nombre social: %s)" % e.nombre_social if e.nombre_social else ""),
                e.rut_formateado, ", ".join(programas(e)) or "—", e.get_estado_display()]
               for i, e in enumerate(estudiantes, start=1)],
              anchos=[28, 250, 85, 100, 77], vacio="El curso no tiene estudiantes.")


def nomina_pdf(cursos):
    """Una página (o más) por curso, en un solo PDF."""
    cursos = list(cursos)
    pdf = DocumentoPDF(*_encabezado_nomina(cursos[0]))
    _tabla_nomina(pdf, cursos[0])
    for curso in cursos[1:]:
        pdf.nueva_pagina(*_encabezado_nomina(curso))
        _tabla_nomina(pdf, curso)
    return pdf


# ---------------------------------------------------------------------------------------------- promoción
FECHA_HABILITA_PROCESO = (11, 1)      # el fin de año se procesa desde el 1 de noviembre


def proceso_del_anio(anio):
    proceso, _ = ProcesoPromocion.objects.get_or_create(anio=anio)
    return proceso


def puede_procesar(proceso, hoy=None):
    hoy = hoy or timezone.localdate()
    return hoy >= datetime.date(proceso.anio, *FECHA_HABILITA_PROCESO)


def validar_terminales(cursos_anio, terminales):
    errores = []
    ids = {c.pk for c in terminales}
    for c in cursos_anio:
        if c.pk not in ids and c.nivel_siguiente() is None:
            errores.append("%s no tiene un nivel siguiente en el colegio: márquelo como curso terminal." % c.nombre)
    if not terminales:
        errores.append("Marque al menos un curso terminal (por ejemplo, 4° Medio).")
    if errores:
        raise ValidationError(errores)


def estudiantes_a_promover(proceso):
    return (Estudiante.objects.filter(curso__anio_escolar=proceso.anio).activos()
            .select_related("curso").order_by("curso__nivel", "apellido_paterno", "apellido_materno"))


@transaction.atomic
def guardar_revision(proceso, repitentes_ids, usuario):
    """Paso 2: deja un resultado propuesto por estudiante (promovido, repite o egresa)."""
    if proceso.procesado:
        raise ValidationError("El proceso de %s ya fue procesado." % proceso.anio)
    terminales = set(proceso.cursos_terminales.values_list("pk", flat=True))
    vigentes = []
    for e in estudiantes_a_promover(proceso):
        if e.pk in repitentes_ids:
            resultado = "repite"
        else:
            resultado = "egresa" if e.curso_id in terminales else "promovido"
        PromocionEstudiante.objects.update_or_create(proceso=proceso, estudiante=e, defaults={
            "curso_origen": e.curso, "curso_destino": None, "resultado": resultado})
        vigentes.append(e.pk)
    proceso.resultados.exclude(estudiante_id__in=vigentes).delete()
    proceso.estado = "revisado"
    proceso.save(update_fields=["estado"])
    registrar(usuario, "modificacion", "proceso_promocion", proceso.pk,
              detalle="revisión: %d repitentes" % len(repitentes_ids))


def _curso_destino(origen, nivel, anio):
    curso, creado = Curso.objects.get_or_create(sede=origen.sede, nivel=nivel, letra=origen.letra, anio_escolar=anio,
                                                defaults={"profesor_jefe": None})
    return curso, creado


def resumen_destinos(proceso):
    """Paso 3: por curso de origen, cuántos pasan a qué curso del año siguiente."""
    filas = {}
    for r in proceso.resultados.select_related("curso_origen", "estudiante"):
        o = r.curso_origen
        fila = filas.setdefault(o.pk, {"origen": o, "promovidos": 0, "repiten": 0, "egresan": 0,
                                       "destino": dict(NIVELES).get(o.nivel_siguiente() or "", "")})
        fila[{"promovido": "promovidos", "repite": "repiten", "egresa": "egresan"}[r.resultado]] += 1
    return sorted(filas.values(), key=lambda f: (f["origen"].orden, f["origen"].letra))


@transaction.atomic
def procesar(proceso, usuario, fecha=None):
    """Paso 3: mueve a los estudiantes a los cursos del año siguiente y registra a los egresados."""
    proceso = ProcesoPromocion.objects.select_for_update().get(pk=proceso.pk)
    if proceso.procesado:
        raise ValidationError("El proceso de %s ya fue procesado." % proceso.anio)
    if proceso.estado != "revisado":
        raise ValidationError("Primero revise la promoción (paso 2).")
    fecha = fecha or timezone.localdate()
    if not puede_procesar(proceso, fecha):
        raise ValidationError("El fin de año se procesa desde el %s." % datetime.date(
            proceso.anio, *FECHA_HABILITA_PROCESO).strftime("%d-%m-%Y"))
    siguiente = proceso.anio + 1
    creados = 0
    for r in proceso.resultados.select_related("estudiante", "curso_origen", "curso_origen__sede"):
        e = r.estudiante
        if r.resultado == "egresa":
            e.fecha_egreso, e.tipo_salida = fecha, "egreso"
            e.full_clean()
            e.save(update_fields=["fecha_egreso", "tipo_salida"])
            continue
        nivel = r.curso_origen.nivel if r.resultado == "repite" else r.curso_origen.nivel_siguiente()
        destino, creado = _curso_destino(r.curso_origen, nivel, siguiente)
        creados += creado
        r.curso_destino = destino
        r.save(update_fields=["curso_destino"])
        e.curso = destino
        e.save(update_fields=["curso"])
    proceso.estado, proceso.fecha_proceso, proceso.procesado_por = "procesado", timezone.now(), usuario
    proceso.save(update_fields=["estado", "fecha_proceso", "procesado_por"])
    registrar(usuario, "modificacion", "proceso_promocion", proceso.pk,
              detalle="fin de año %s procesado; %d cursos creados para %s" % (proceso.anio, creados, siguiente))
    return creados
