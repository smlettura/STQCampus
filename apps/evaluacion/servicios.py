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
