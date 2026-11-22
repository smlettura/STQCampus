"""Tareas programadas de la plataforma. En AWS las dispara EventBridge Scheduler mediante Systems Manager Run Command,
que ejecuta en la instancia «python manage.py ejecutar_tarea diaria|mensual»."""
import datetime

from django.utils import timezone


def tarea_diaria():
    from apps.auditoria.servicios import exportar_dia
    from apps.evaluacion.servicios import procesar_reevaluaciones

    return {"avisos_reevaluacion": procesar_reevaluaciones(),
            "bitacora_exportada": exportar_dia(timezone.localdate() - datetime.timedelta(days=1))[1]}


def tarea_mensual():
    from apps.cumplimiento.models import RetencionEliminacion
    from apps.cumplimiento.servicios import ejecutar, proponer_retenciones

    ejecutadas = 0
    for r in RetencionEliminacion.objects.filter(estado="autorizada", autorizada_por__isnull=False):
        ejecutar(r)
        ejecutadas += 1
    return {"retenciones_propuestas": proponer_retenciones(), "retenciones_ejecutadas": ejecutadas}


TAREAS = {"diaria": tarea_diaria, "mensual": tarea_mensual}
