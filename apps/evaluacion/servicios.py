"""Control de plazos de reevaluación (RF-08, BPMN B5): tarea programada diaria."""
import datetime

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.alertas.servicios import usuarios_con_rol
from apps.auditoria.servicios import registrar
from apps.core.avisos import avisar_al_confirmar

from .models import AvisoReevaluacion, EvaluacionDiagnostica


def evaluaciones_por_reevaluar(hoy=None):
    """Evaluaciones cerradas cuya reevaluación vence dentro del plazo de aviso (o ya venció) y que no tienen una
    reevaluación posterior registrada en el mismo caso."""
    hoy = hoy or timezone.localdate()
    limite = hoy + datetime.timedelta(days=settings.AVISO_REEVALUACION_DIAS)
    candidatas = EvaluacionDiagnostica.objects.filter(estado="cerrada", fecha_reevaluacion__isnull=False,
                                                      fecha_reevaluacion__lte=limite).select_related("caso")
    resultado = []
    for ev in candidatas:
        posterior = EvaluacionDiagnostica.objects.filter(caso=ev.caso, tipo_evaluacion="reevaluacion",
                                                         fecha_evaluacion__gt=ev.fecha_evaluacion).exists()
        if not posterior and not ev.caso.cerrado:
            resultado.append(ev)
    return resultado


@transaction.atomic
def procesar_reevaluaciones(hoy=None):
    hoy = hoy or timezone.localdate()
    destinatarios = list(usuarios_con_rol("coordinacion_pie"))
    creados = 0
    for ev in evaluaciones_por_reevaluar(hoy):
        for usuario in destinatarios + [ev.caso.responsable]:
            aviso, nuevo = AvisoReevaluacion.objects.get_or_create(
                evaluacion=ev, destinatario=usuario,
                defaults={"fecha_programada": ev.fecha_reevaluacion, "fecha_envio": timezone.now(), "estado": "enviado"})
            if nuevo:
                creados += 1
                registrar(None, "creacion", "aviso_reevaluacion", aviso.pk)
                avisar_al_confirmar([usuario], "Reevaluación PIE próxima a vencer", reverse("evaluacion:avisos"))
    # Los avisos se dan por atendidos cuando se registra la reevaluación correspondiente.
    for aviso in AvisoReevaluacion.objects.exclude(estado="atendido").select_related("evaluacion"):
        if EvaluacionDiagnostica.objects.filter(caso_id=aviso.evaluacion.caso_id, tipo_evaluacion="reevaluacion",
                                                fecha_evaluacion__gt=aviso.evaluacion.fecha_evaluacion).exists():
            aviso.estado = "atendido"
            aviso.save(update_fields=["estado"])
    return creados


# ------------------------------------------------------------------ RF-06: versión preliminar del FUDEI
def _fecha(f):
    return f.strftime("%d-%m-%Y") if f else "—"


def borrador_preliminar_fudei(caso):
    """Texto inicial de la versión preliminar del FUDEI armado con los datos ya registrados (RF-06, apoyo interno).

    Lo que exige juicio profesional queda como [PENDIENTE: …]; el informe no se puede validar mientras quede una marca.
    El FUDEI oficial se sigue completando en el formato vigente del Mineduc."""
    e = caso.estudiante
    ev = caso.evaluaciones.order_by("-fecha_evaluacion", "-id").first()
    lineas = [
        "VERSIÓN PRELIMINAR DEL FUDEI — APOYO INTERNO",
        "Preparada el %s con los datos registrados en la plataforma. El FUDEI oficial se completa en el formato "
        "vigente del Mineduc." % _fecha(timezone.localdate()),
        "",
        "1. Identificación del estudiante",
        "Nombre: %s" % e.nombre_completo,
        "RUT: %s" % e.rut_formateado,
        "Fecha de nacimiento: %s%s" % (_fecha(e.fecha_nacimiento), " (%s años)" % e.edad if e.edad is not None else ""),
        "Curso: %s" % e.curso,
        "Necesidad educativa registrada: %s" % e.get_necesidad_educativa_display(),
        "Programas: %s" % (", ".join(p for p, si in (("PIE", e.en_pie), ("Prioritario (SEP)", e.prioritario)) if si)
                           or "Sin programas registrados"),
        "",
        "2. Tipo y motivo de la evaluación",
    ]
    if ev:
        lineas += ["Tipo de evaluación: %s" % ev.get_tipo_evaluacion_display(),
                   "Fecha de evaluación: %s" % _fecha(ev.fecha_evaluacion),
                   "Próxima reevaluación: %s" % _fecha(ev.fecha_reevaluacion)]
    else:
        lineas.append("[PENDIENTE: el caso no tiene una evaluación diagnóstica registrada]")
    derivacion = caso.derivaciones.order_by("-id").first()
    lineas.append("Motivo: %s" % (derivacion.motivo if derivacion else "[PENDIENTE: motivo de la evaluación]"))
    lineas += ["", "3. Profesionales que participaron"]
    participaciones = list(ev.participaciones.select_related("usuario").order_by("fecha")) if ev else []
    if participaciones:
        lineas += ["- %s (%s, %s): %s" % (p.usuario.nombre_completo, p.rol_profesional, _fecha(p.fecha), p.aporte)
                   for p in participaciones]
    else:
        lineas.append("[PENDIENTE: profesionales que participaron y sus aportes]")
    lineas += ["", "4. Síntesis diagnóstica"]
    if ev:
        lineas.append("Tipo de NEE: %s" % ev.tipo_nee)
        lineas.append("Diagnóstico integral: %s" % (ev.diagnostico or "[PENDIENTE: síntesis del diagnóstico integral]"))
    else:
        lineas.append("[PENDIENTE: tipo de NEE y síntesis del diagnóstico integral]")
    lineas += ["", "5. Apoyos y adecuaciones"]
    planes = list(e.planes.filter(estado="vigente").order_by("-fecha_inicio"))
    if planes:
        lineas += ["- %s desde el %s: %s" % (p.get_tipo_display(), _fecha(p.fecha_inicio), p.adecuaciones) for p in planes]
    else:
        lineas.append("[PENDIENTE: apoyos y adecuaciones que se proponen]")
    lineas += ["", "6. Observaciones del equipo",
               "[PENDIENTE: observaciones y acuerdos del equipo de aula]"]
    return "\n".join(lineas)
