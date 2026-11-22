"""Mensajes que recibe el modelo: el prompt v4 del módulo de IA (apps/ia/motor.py, probado en LOC-02/LOC-05) y la
plantilla del borrador, armados con las atenciones elegidas. Es el único lugar que arma lo que va al modelo.

Las condiciones de la profesional pasan por `guardas.filtrar_condiciones` (solo formato) y las órdenes escondidas en
las notas por `guardas.neutralizar_inyecciones` antes de seudonimizar (ver servicios.crear_solicitud).
"""
from django.conf import settings
from django.utils import timezone

from . import motor

VERSION_PROMPT = motor.VERSION_PROMPT
TITULOS_TIPO = {"atencion": "Informe de atención", "derivacion_externa": "Derivación externa",
                "apoderado": "Informe para apoderado", "direccion": "Informe para dirección",
                "cronologico": "Línea de tiempo del caso"}
DESTINATARIOS = {"atencion": "Equipo psicosocial (ficha del estudiante)",
                 "derivacion_externa": "Red de salud o institución externa",
                 "apoderado": "Apoderado del estudiante", "direccion": "Dirección del establecimiento",
                 "cronologico": "Equipo psicosocial (ficha del estudiante)"}
TITULOS_SECCION = {"antecedentes": "Antecedentes", "desarrollo": "Desarrollo de las sesiones",
                   "acuerdos": "Acuerdos y compromisos", "sugerencias": "Sugerencias de seguimiento",
                   "cronologico": "Resumen cronologico; Documentos de evidencia"}


def texto_secciones(secciones):
    return "; ".join(TITULOS_SECCION[s] for s in secciones)


def texto_antecedentes(estudiante, caso):
    """Antecedentes registrados en la ficha y en el caso: sin ellos el modelo no tiene con qué redactar
    «Antecedentes» y deja [PENDIENTE]. Se entregan como un registro más, así el modelo puede usarlos (regla 11)."""
    e = estudiante
    datos = ["%s %s" % (e.nombres, e.apellidos)]
    if e.edad is not None:
        datos.append("%s años" % e.edad)
    datos.append("curso %s" % e.curso.nombre)
    datos.append("necesidad educativa: %s" % e.get_necesidad_educativa_display())
    if e.en_pie:
        datos.append("participa en el Programa de Integración Escolar")
    lineas = ["A · Antecedentes registrados en la ficha: " + "; ".join(datos) + "."]
    if caso is not None:
        lineas.append("A · Caso de %s abierto el %s (estado: %s)." % (
            caso.get_tipo_proceso_display().lower(), caso.fecha_apertura.strftime("%d/%m/%Y"),
            caso.get_estado_display().lower()))
        for d in caso.derivaciones.select_related("derivante").order_by("fecha_hora"):
            lineas.append("A · Derivación del %s por %s: %s" % (timezone.localtime(d.fecha_hora).strftime("%d/%m/%Y"),
                                                              d.derivante.nombre_completo, (d.motivo or "").strip()))
        for h in caso.hitos.order_by("fecha"):
            lineas.append("A · %s (%s): %s" % (h.get_tipo_display(), h.fecha.strftime("%d/%m/%Y"), h.descripcion.strip()))
    for p in e.planes.filter(estado="vigente"):
        lineas.append("A · Plan de apoyo vigente (%s) desde el %s. Adecuaciones: %s" % (
            p.get_tipo_display(), p.fecha_inicio.strftime("%d/%m/%Y"), (p.adecuaciones or "").strip()))
    return "\n".join(lineas)


def texto_registros(caso, usuario, desde):
    """Registros del caso para la línea de tiempo (RF-17), con las mismas reglas de acceso que la ficha del caso."""
    from apps.casos.servicios import linea_de_tiempo
    lineas = []
    for i in sorted(linea_de_tiempo(caso, usuario), key=lambda x: x["fecha"]):
        if i.get("borrador") or i["fecha"].date() < desde:
            continue
        texto = (i.get("texto") or "").strip()
        if i.get("detalle"):
            texto = "%s. %s" % (i["detalle"], texto)
        autor = " (%s)" % i["autor"] if i.get("autor") else ""
        lineas.append("%s · %s%s: %s" % (i["fecha"].strftime("%d/%m/%Y"), i["etiqueta"], autor, texto or "(sin descripción)"))
    return "\n".join(lineas)


def texto_notas(sesiones):
    """Mismo formato que en las pruebas del módulo de IA: «R1 · dd/mm/aaaa · título (motivo): nota Acuerdos: …»."""
    lineas = []
    for i, s in enumerate(sorted(sesiones, key=lambda x: x.fecha_hora), 1):
        cuerpo = (s.nota or "").strip()
        if (s.acuerdos or "").strip():
            cuerpo = (cuerpo + " " if cuerpo else "") + "Acuerdos: " + s.acuerdos.strip()
        lineas.append("R%d · %s · %s (%s): %s" % (i, timezone.localtime(s.fecha_hora).strftime("%d/%m/%Y"), s.titulo,
                                                  s.get_motivo_display(), cuerpo or "(sin descripción)"))
    return "\n".join(lineas)


def condiciones_fijas(secciones):
    """Condiciones que agrega la plataforma (confiables)."""
    if "sugerencias" in secciones:
        return "En «Sugerencias de seguimiento» incluye únicamente lo que el equipo ya acordó en las notas"
    return ""


def construir_entrada(sesiones, tipo, secciones, condiciones_filtradas="Ninguna.", estudiante=None, caso=None,
                      usuario=None, desde=None):
    """Texto con datos reales (se neutralizan órdenes y se seudonimiza después, antes de salir de AWS)."""
    if tipo == "cronologico":
        hoy = timezone.localdate()
        return motor.PLANTILLA_RESUMEN.format(
            desde=desde.strftime("%d/%m/%Y"), hasta=hoy.strftime("%d/%m/%Y"), condiciones=condiciones_filtradas,
            registros=texto_registros(caso, usuario, desde))
    notas = texto_notas(sesiones)
    if estudiante is not None:
        notas = texto_antecedentes(estudiante, caso) + "\n" + notas
    return motor.PLANTILLA_BORRADOR.format(
        tipo=TITULOS_TIPO[tipo], destinatario=DESTINATARIOS[tipo], secciones=texto_secciones(secciones),
        condiciones=motor._unir_condiciones(condiciones_fijas(secciones), condiciones_filtradas),
        notas=notas, fragmentos="Ninguno.")


def construir_mensajes(entrada_seudonimizada, aviso=""):
    """Mensajes para /api/chat de Ollama: prompt de sistema v4 y entrada + recordatorio final (+ aviso si se reintenta)."""
    sistema, refuerzo = motor.PROMPTS[VERSION_PROMPT]
    return [{"role": "system", "content": sistema},
            {"role": "user", "content": entrada_seudonimizada + refuerzo + aviso}]


def opciones():
    """Parámetros de generación iguales a los de las pruebas (motor.ConfigIA). num_gpu=0: solo CPU, como se midió."""
    c = motor.ConfigIA()
    o = {"temperature": c.temperature, "num_ctx": c.num_ctx, "num_predict": c.num_predict}
    num_gpu = getattr(settings, "IA_NUM_GPU", c.num_gpu)
    if num_gpu is not None:
        o["num_gpu"] = num_gpu
    return o


def aviso_reintento(hallazgos):
    from . import guardas
    return ("\n\nAVISO: tu version anterior incluyo contenido fuera de tus limites ("
            + "; ".join(guardas.DESCRIPCION[h.codigo] for h in hallazgos)
            + "). Redactala de nuevo sin ese contenido y, en su lugar, escribe «[FUERA DE MI ALCANCE: ...]».")
