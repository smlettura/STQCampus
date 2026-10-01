"""Datos de la pantalla «Atención psicosocial › Resumen» del prototipo v1 (solo cifras agregadas y listas operativas)."""
import datetime

from django.db.models import Count
from django.utils import timezone

from apps.core.filtros import MESES
from apps.core.validadores import inicio_del_dia
from apps.estudiantes.models import TRAMO_CONVIVENCIA, Estudiante

from .acceso import casos_visibles
from .models import Caso, Derivacion, SesionSeguimiento
from .servicios import casos_urgentes

TIPOS_ANOTACION = [("positiva", "Positivas", "verde"), ("moderada", "Moderadas", "ambar"), ("grave", "Graves", "naranjo"),
                   ("gravisima", "Gravísimas", "rojo")]


def anotaciones_por_tipo(qs):
    conteo = dict(qs.values_list("tipo").annotate(n=Count("id")))
    total = sum(conteo.values())
    maximo = max(conteo.values(), default=0) or 1
    return total, [{"clave": c, "etiqueta": e, "color": color, "valor": conteo.get(c, 0),
                    "ancho": round(100 * conteo.get(c, 0) / maximo, 1),
                    "porcentaje": round(100 * conteo.get(c, 0) / total) if total else 0}
                   for c, e, color in TIPOS_ANOTACION]


def datos_resumen(usuario, f):
    from apps.alertas.acceso import alertas_visibles
    from apps.convivencia.models import Anotacion, Conflicto, ProtocoloActivado

    hoy = timezone.localdate()
    estudiantes = Estudiante.objects.filter(curso__anio_escolar=f.anio).exclude(tipo_salida="egreso")
    if f.curso:
        estudiantes = estudiantes.filter(curso=f.curso)
    # Mes de las atenciones: el elegido en el filtro o, si no hay, el mes en curso (o diciembre de un año pasado).
    mes = f.mes or (hoy.month if f.anio == hoy.year else 12)
    inicio = datetime.date(f.anio, mes, 1)
    fin = datetime.date(f.anio + (mes == 12), mes % 12 + 1, 1)
    atenciones = SesionSeguimiento.objects.filter(estado="registrada", fecha_hora__gte=inicio_del_dia(inicio),
                                                  fecha_hora__lt=inicio_del_dia(fin))
    casos = Caso.objects.all()
    if f.curso:
        atenciones = atenciones.filter(caso__estudiante__curso=f.curso)
        casos = casos.filter(estudiante__curso=f.curso)
    abiertos = casos.exclude(estado="cerrado")
    urgentes = casos_urgentes(casos)

    conflictos = f.filtrar_fecha(Conflicto.objects.select_related("curso", "encargada"), "fecha")
    anotaciones = f.filtrar_fecha(Anotacion.objects.filter(estudiante__curso__anio_escolar=f.anio), "fecha")
    if f.curso:
        conflictos = conflictos.filter(curso=f.curso)
        anotaciones = anotaciones.filter(estudiante__curso=f.curso)
    tramos = {"basica": 0, "media": 0}
    for nivel in conflictos.values_list("curso__nivel", flat=True):
        tramo = TRAMO_CONVIVENCIA.get(nivel)
        if tramo in tramos:
            tramos[tramo] += 1
    total_anotaciones, por_tipo = anotaciones_por_tipo(anotaciones)

    alertas_sin_revisar = alertas_visibles(usuario).filter(estado="registrada").count() \
        if usuario.tiene_permiso("alerta.gestionar", "alerta.ver_constancias") else None
    ve_convivencia = usuario.tiene_permiso("convivencia.ver")
    datos = {
        "matriculados": estudiantes.count(), "activos": estudiantes.activos().count(),
        "atenciones_mes": atenciones.count(), "nombre_mes": MESES[mes - 1],
        "en_seguimiento": abiertos.values("estudiante").distinct().count(),
        "conflictos": conflictos.count(), "tramos": tramos, "urgentes": urgentes.count(),
        "total_anotaciones": total_anotaciones, "anotaciones_por_tipo": por_tipo,
        "protocolos_abiertos": ProtocoloActivado.objects.filter(estado="abierto").count()
        if usuario.tiene_permiso("protocolo.ver", "protocolo.gestionar") else None,
        "alertas_sin_revisar": alertas_sin_revisar,
        "ve_convivencia": ve_convivencia,
        "mediaciones": list(conflictos.filter(tipo_gestion="mediacion").annotate(n=Count("participantes"))
                           .order_by("-fecha", "-id")[:3])
        if ve_convivencia else [],
    }
    # Trabajo propio de la profesional (no aparece en el prototipo, pero lo exigen los requisitos RF-01 a RF-04).
    if usuario.tiene_permiso("caso.gestionar"):
        datos["n_derivaciones"] = Derivacion.objects.filter(caso__isnull=True).count()
        datos["derivaciones_pendientes"] = (Derivacion.objects.filter(caso__isnull=True)
                                            .select_related("estudiante", "estudiante__curso", "derivante")[:6])
        datos["mis_casos"] = (casos_visibles(usuario).filter(responsable=usuario).exclude(estado="cerrado")
                              .select_related("estudiante", "estudiante__curso")[:6])
        datos["mis_borradores"] = (SesionSeguimiento.objects.filter(profesional=usuario, estado="borrador")
                                   .select_related("caso__estudiante")[:6])
    if usuario.tiene_permiso("evaluacion.gestionar"):
        from apps.evaluacion.models import AvisoReevaluacion
        datos["avisos"] = (AvisoReevaluacion.objects.filter(destinatario=usuario).exclude(estado="atendido")
                           .select_related("evaluacion__caso__estudiante")[:6])
    return datos
