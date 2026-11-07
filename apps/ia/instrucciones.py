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
                "apoderado": "Informe para apoderado", "direccion": "Informe para dirección"}
DESTINATARIOS = {"atencion": "Equipo psicosocial (ficha del estudiante)",
                 "derivacion_externa": "Red de salud o institución externa",
                 "apoderado": "Apoderado del estudiante", "direccion": "Dirección del establecimiento"}
TITULOS_SECCION = {"antecedentes": "Antecedentes", "desarrollo": "Desarrollo de las sesiones",
                   "acuerdos": "Acuerdos y compromisos", "sugerencias": "Sugerencias de seguimiento"}


def texto_secciones(secciones):
    return "; ".join(TITULOS_SECCION[s] for s in secciones)


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


def construir_entrada(sesiones, tipo, secciones, condiciones_filtradas="Ninguna."):
    """Texto con datos reales (se neutralizan órdenes y se seudonimiza después, antes de salir de AWS)."""
    return motor.PLANTILLA_BORRADOR.format(
        tipo=TITULOS_TIPO[tipo], destinatario=DESTINATARIOS[tipo], secciones=texto_secciones(secciones),
        condiciones=motor._unir_condiciones(condiciones_fijas(secciones), condiciones_filtradas),
        notas=texto_notas(sesiones), fragmentos="Ninguno.")


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
