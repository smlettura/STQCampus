"""Texto de entrada del copiloto: datos que arma la plataforma y la instrucción por tipo de informe.

El prompt de sistema, los límites y los ejemplos están en el Modelfile del equipo propio (docs/ia/Modelfile). Aquí solo
se arma el mensaje de cada solicitud. AJUSTAR al formato con que el equipo de IA probó el modelo en LOC-05 cuando se
reciba su exportación: es el único lugar que hay que cambiar.
"""
from django.utils import timezone

TITULOS_TIPO = {"atencion": "Informe de atención psicosocial", "derivacion_externa": "Informe de derivación externa",
                "apoderado": "Informe para el apoderado", "direccion": "Informe para Dirección"}
TITULOS_SECCION = {"antecedentes": "Antecedentes", "desarrollo": "Desarrollo de las sesiones",
                   "acuerdos": "Acuerdos y compromisos", "sugerencias": "Sugerencias de seguimiento"}
INDICACIONES_TIPO = {
    "atencion": "Destinatario: el equipo psicosocial. Registro técnico y objetivo de lo trabajado.",
    "derivacion_externa": "Destinatario: un profesional externo. Resume motivo, intervenciones y razón de la derivación.",
    "apoderado": "Destinatario: la familia. Lenguaje claro, respetuoso y sin términos técnicos innecesarios.",
    "direccion": "Destinatario: Dirección. Breve, centrado en acciones, acuerdos y apoyos requeridos.",
}


def construir_entrada(estudiante, sesiones, tipo, secciones, hoy=None):
    """Texto con datos reales (se seudonimiza después, antes de salir de AWS)."""
    hoy = hoy or timezone.localdate()
    e = estudiante
    lineas = ["Tipo de informe: %s." % TITULOS_TIPO[tipo], INDICACIONES_TIPO[tipo],
              "Secciones solicitadas, en este orden: %s." % "; ".join(TITULOS_SECCION[s] for s in secciones),
              "", "Estudiante: %s %s, %s años, %s, %s%s." % (
                  e.nombres, e.apellidos, e.edad if e.edad is not None else "edad no registrada", e.curso.nombre,
                  e.get_necesidad_educativa_display(), ", participa en el PIE" if e.en_pie else ""),
              "", "Atenciones seleccionadas por la profesional (de la más antigua a la más reciente):"]
    for i, s in enumerate(sorted(sesiones, key=lambda x: x.fecha_hora), 1):
        lineas.append("%d. %s · %s · %s minutos · Motivo: %s%s" % (
            i, timezone.localtime(s.fecha_hora).strftime("%d-%m-%Y"), s.get_tipo_atencion_display(), s.duracion_minutos,
            s.get_motivo_display(), " · Derivado por: %s" % s.get_derivado_por_display() if s.derivado_por else ""))
        if s.nota:
            lineas.append("   Descripción: %s" % s.nota.strip())
        if s.acuerdos:
            lineas.append("   Acuerdos: %s" % s.acuerdos.strip())
    return "\n".join(lineas)


def construir_mensajes(texto_seudonimizado, secciones):
    """Mensajes para /api/chat de Ollama. El agente los envía tal cual al modelo del Modelfile."""
    formato = "\n".join("## %s" % TITULOS_SECCION[s] for s in secciones)
    instruccion = (
        "Redacta un BORRADOR en español de Chile usando solo la información entregada. No inventes hechos, "
        "diagnósticos ni conclusiones clínicas. Mantén los marcadores entre corchetes (por ejemplo, [ESTUDIANTE]) "
        "exactamente como aparecen. Usa estos títulos, en este orden:\n%s\n\nDatos:\n%s" % (formato, texto_seudonimizado))
    return [{"role": "user", "content": instruccion}]
