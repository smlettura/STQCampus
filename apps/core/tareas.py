"""Tareas programadas de la plataforma. En AWS las dispara EventBridge Scheduler mediante Systems Manager Run Command,
que ejecuta en la instancia «python manage.py ejecutar_tarea diaria|mensual»."""
import datetime

from django.utils import timezone


DIAS_RECUPERACION = 60


def dias_por_exportar(hoy=None):
    """Días cerrados cuya copia de la bitácora todavía no existe. Si el servidor estuvo apagado cuando tocaba la
    tarea (en AWS Academy la instancia se suspende al terminar cada sesión), los días pendientes se recuperan en la
    siguiente ejecución. Se revisan como máximo DIAS_RECUPERACION días y nunca antes del primer evento registrado."""
    from apps.auditoria.models import EventoAuditoria

    hoy = hoy or timezone.localdate()
    primero = EventoAuditoria.objects.order_by("id").values_list("fecha_hora", flat=True).first()
    if primero is None:
        return []
    desde = max(timezone.localtime(primero).date(), hoy - datetime.timedelta(days=DIAS_RECUPERACION))
    return [desde + datetime.timedelta(days=i) for i in range((hoy - desde).days)]


def tarea_diaria():
    """Avisos de reevaluación y copia de la bitácora. Se puede ejecutar varias veces al día: los avisos no se
    duplican y los días ya copiados se omiten."""
    from apps.auditoria.servicios import exportar_dia
    from apps.evaluacion.servicios import procesar_reevaluaciones

    eventos, dias = 0, []
    for fecha in dias_por_exportar():
        _, n = exportar_dia(fecha)
        eventos += n
        dias.append(fecha.isoformat())
    return {"avisos_reevaluacion": procesar_reevaluaciones(), "bitacora_exportada": eventos, "dias_revisados": len(dias)}


def tarea_mensual():
    from apps.cumplimiento.models import RetencionEliminacion
    from apps.cumplimiento.servicios import ejecutar, proponer_retenciones

    ejecutadas = 0
    for r in RetencionEliminacion.objects.filter(estado="autorizada", autorizada_por__isnull=False):
        ejecutar(r)
        ejecutadas += 1
    return {"retenciones_propuestas": proponer_retenciones(), "retenciones_ejecutadas": ejecutadas}


TAREAS = {"diaria": tarea_diaria, "mensual": tarea_mensual}
