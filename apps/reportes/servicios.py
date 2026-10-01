"""Indicadores agregados de gestión (RF-15). Solo cifras: ningún reporte expone nombres ni contenido clínico."""
import datetime

from django.db.models import Avg, Count, F
from django.utils import timezone

from apps.alertas.models import TIPOS_SITUACION, AlertaRiesgo, Denuncia
from apps.casos.models import Caso, Derivacion, SesionSeguimiento
from apps.core.filtros import MESES
from apps.core.validadores import inicio_del_dia
from apps.cumplimiento.models import SolicitudARCO
from apps.evaluacion.servicios import evaluaciones_por_reevaluar


def _serie(conteos, etiquetas):
    total = max([c for c in conteos.values()] + [1])
    return [{"clave": k, "etiqueta": v, "valor": conteos.get(k, 0), "porcentaje": round(100 * conteos.get(k, 0) / total)}
            for k, v in etiquetas]


def atenciones(desde, hasta):
    """Estadísticas de atenciones registradas en el periodo (cifras agregadas, sin contenido de las sesiones)."""
    qs = SesionSeguimiento.objects.filter(estado="registrada", fecha_hora__gte=inicio_del_dia(desde),
                                          fecha_hora__lt=inicio_del_dia(hasta + datetime.timedelta(days=1)))
    # El mes se calcula en Python (hora de Chile): así no depende de las tablas de zonas horarias de MySQL.
    por_mes = {}
    for fecha_hora in qs.values_list("fecha_hora", flat=True):
        m = timezone.localtime(fecha_hora).month
        por_mes[m] = por_mes.get(m, 0) + 1
    meses = [(m, MESES[m - 1][:3].capitalize()) for m in range(desde.month, hasta.month + 1)] \
        if desde.year == hasta.year else [(m, MESES[m - 1][:3].capitalize()) for m in range(1, 13)]
    return {
        "total": qs.count(),
        "estudiantes": qs.values("caso__estudiante").distinct().count(),
        "duracion_promedio": round(qs.aggregate(p=Avg("duracion_minutos"))["p"] or 0),
        "urgencia_alta": qs.filter(urgencia="alta").count(),
        "por_mes": _serie(por_mes, meses),
        "por_motivo": sorted(_serie(dict(qs.values_list("motivo").annotate(n=Count("id"))), SesionSeguimiento.MOTIVOS),
                             key=lambda x: -x["valor"]),
        "por_tipo": _serie(dict(qs.values_list("tipo_atencion").annotate(n=Count("id"))), SesionSeguimiento.TIPOS),
        "por_urgencia": _serie(dict(qs.values_list("urgencia").annotate(n=Count("id"))), SesionSeguimiento.URGENCIAS),
    }


def resumen(desde=None, hasta=None):
    hoy = timezone.localdate()
    desde = desde or hoy - datetime.timedelta(days=365)
    hasta = max(min(hasta or hoy, hoy), desde)
    t0 = inicio_del_dia(desde)
    t1 = inicio_del_dia(hasta + datetime.timedelta(days=1))
    activos = Caso.objects.exclude(estado="cerrado")
    por_tipo = dict(activos.values_list("tipo_proceso").annotate(n=Count("id")))
    por_estado = dict(Caso.objects.values_list("estado").annotate(n=Count("id")))

    alertas = AlertaRiesgo.objects.filter(fecha_hora_registro__gte=t0, fecha_hora_registro__lt=t1)
    alertas_tipo = dict(alertas.values_list("tipo_situacion").annotate(n=Count("id")))
    denuncias = list(Denuncia.objects.filter(alerta__fecha_hora_registro__gte=t0, alerta__fecha_hora_registro__lt=t1)
                     .select_related("alerta"))
    en_plazo = sum(1 for d in denuncias if d.dentro_de_plazo)

    derivaciones = Derivacion.objects.filter(caso__isnull=False, fecha_hora__gte=t0, fecha_hora__lt=t1).annotate(
        apertura=F("caso__fecha_apertura"))
    dias = [(d.apertura - timezone.localtime(d.fecha_hora).date()).days for d in derivaciones]

    por_reevaluar = evaluaciones_por_reevaluar(hoy)
    return {
        "periodo": {"desde": desde.isoformat(), "hasta": hasta.isoformat()},
        "casos_activos": activos.count(),
        "casos_por_tipo": _serie(por_tipo, Caso.TIPOS_PROCESO),
        "casos_por_estado": _serie(por_estado, Caso.ESTADOS),
        "derivaciones_pendientes": Derivacion.objects.filter(caso__isnull=True).count(),
        "dias_promedio_derivacion_a_caso": round(sum(dias) / len(dias), 1) if dias else None,
        "reevaluaciones_vencidas": sum(1 for e in por_reevaluar if e.fecha_reevaluacion < hoy),
        "reevaluaciones_proximas": sum(1 for e in por_reevaluar if e.fecha_reevaluacion >= hoy),
        "alertas_total": alertas.count(),
        "alertas_abiertas": alertas.exclude(estado="cerrada").count(),
        "alertas_por_tipo": _serie(alertas_tipo, TIPOS_SITUACION),
        "denuncias": len(denuncias), "denuncias_en_plazo": en_plazo,
        "arco_pendientes": SolicitudARCO.objects.filter(estado__in=["recibida", "en_analisis"]).count(),
        "arco_vencidas": SolicitudARCO.objects.filter(estado__in=["recibida", "en_analisis"], fecha_limite__lt=hoy).count(),
        "atenciones": atenciones(desde, hasta),
        "modulo_ia": "en entrenamiento",
    }
