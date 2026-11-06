"""Cálculos de las pantallas de convivencia: gráfico de anotaciones por curso, indicadores de bienestar, protocolos
activados desde alertas y evidencias cifradas del plan de gestión."""
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.html import escape

from apps.auditoria.servicios import registrar
from apps.casos import almacenamiento
from apps.core.validadores import nombre_archivo_seguro
from apps.estudiantes.models import ABREVIATURA, CICLO, GRUPO_ENSENANZA, NIVELES

from .models import EvidenciaActividad, ProtocoloActivado

COLORES_ANOTACION = [("positiva", "Positivas", "verde"), ("moderada", "Moderadas", "ambar"), ("grave", "Graves", "naranjo"),
                     ("gravisima", "Gravísimas", "rojo")]
CICLOS = [("", "Todos"), ("prebasica", "Prebásica"), ("ciclo1", "1° ciclo"), ("ciclo2", "2° ciclo"), ("media", "Media")]


# ---------------------------------------------------------------------------------------------- anotaciones por curso
def anotaciones_por_curso(anotaciones, ciclo=""):
    """Filas por nivel (PK a 4°M) con el conteo de cada tipo. Si hay varias letras por nivel se suman."""
    conteo = {}
    for nivel, tipo, n in anotaciones.values_list("estudiante__curso__nivel", "tipo").annotate(n=Count("id")):
        conteo.setdefault(nivel, {})[tipo] = n
    filas = []
    for nivel, _ in NIVELES:
        if ciclo and CICLO.get(nivel) != ciclo:
            continue
        valores = [conteo.get(nivel, {}).get(t, 0) for t, _, _ in COLORES_ANOTACION]
        filas.append({"nivel": nivel, "etiqueta": ABREVIATURA[nivel], "valores": valores, "total": sum(valores)})
    return filas


def _escala(maximo):
    """Máximo del eje redondeado hacia arriba a un número «bonito» y el paso de las líneas guía."""
    if maximo <= 0:
        return 4, 1
    for paso in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000, 10000):
        if maximo <= paso * 4:
            return paso * 4, paso
    paso = 10 ** len(str(int(maximo)))
    return paso * 4, paso


def grafico_barras_apiladas(filas):
    """SVG de barras apiladas (una por curso), accesible y sin JavaScript, como en el prototipo v1."""
    ancho, alto, izq, abajo, arriba = 1000, 360, 48, 30, 12
    alto_util = alto - abajo - arriba
    maximo, paso = _escala(max([f["total"] for f in filas] + [0]))
    n = max(len(filas), 1)
    hueco = (ancho - izq) / n
    barra = min(46, hueco * 0.58)
    partes = ['<svg class="grafico" viewBox="0 0 %d %d" role="img" aria-labelledby="titulo-grafico">' % (ancho, alto),
              '<title id="titulo-grafico">Anotaciones por curso, apiladas por tipo</title>']
    for valor in range(paso, maximo + 1, paso):
        y = arriba + alto_util * (1 - valor / maximo)
        partes.append('<line class="guia" x1="%d" x2="%d" y1="%.1f" y2="%.1f"/>' % (izq, ancho, y, y))
        partes.append('<text class="eje" x="0" y="%.1f">%d</text>' % (y + 4, valor))
    for i, f in enumerate(filas):
        x = izq + hueco * i + (hueco - barra) / 2
        base_y = arriba + alto_util
        partes.append('<line class="base" x1="%.1f" x2="%.1f" y1="%.1f" y2="%.1f"/>' % (x - 4, x + barra + 4, base_y, base_y))
        detalle = ", ".join("%s: %d" % (nombre, v) for (_, nombre, _), v in zip(COLORES_ANOTACION, f["valores"]))
        partes.append('<g><title>%s — %s</title>' % (escape(f["etiqueta"]), escape(detalle)))
        for (_, _, color), v in zip(COLORES_ANOTACION, f["valores"]):
            if not v:
                continue
            h = alto_util * v / maximo
            base_y -= h
            partes.append('<rect class="%s" x="%.1f" y="%.1f" width="%.1f" height="%.1f"/>' % (color, x, base_y, barra, h))
        partes.append('</g>')
        partes.append('<text class="eje" x="%.1f" y="%d" text-anchor="middle">%s</text>' % (
            x + barra / 2, alto - 8, escape(f["etiqueta"])))
    partes.append("</svg>")
    return "".join(partes)


# ---------------------------------------------------------------------------------------------- protocolos
def nivel_de(curso):
    return {"prebasica": "Prebásica", "basica": "Básica", "media": "Media"}.get(GRUPO_ENSENANZA.get(curso.nivel), "")


@transaction.atomic
def activar_desde_alerta(alerta, usuario, fecha=None):
    """Al registrar «protocolo activado» en una alerta se crea el protocolo del reglamento que corresponde."""
    codigo = ProtocoloActivado.DESDE_ALERTA.get(alerta.tipo_situacion)
    if not codigo or ProtocoloActivado.objects.filter(alerta=alerta, protocolo=codigo).exists():
        return None
    protocolo = ProtocoloActivado(protocolo=codigo, fecha_activacion=fecha or timezone.localdate(),
                                  curso=alerta.estudiante.curso, estudiante=alerta.estudiante, responsable=usuario,
                                  alerta=alerta, observaciones="Activado desde la alerta de riesgo N° %d." % alerta.pk)
    protocolo.full_clean()
    protocolo.save()
    registrar(usuario, "creacion", "protocolo_activado", protocolo.pk, detalle="desde alerta %d" % alerta.pk)
    return protocolo


# ---------------------------------------------------------------------------------------------- evidencias
def guardar_evidencia(archivo, actividad, usuario):
    ruta_objeto, huella = almacenamiento.guardar_bytes(b"".join(archivo.chunks()))
    evidencia = EvidenciaActividad.objects.create(actividad=actividad, nombre_archivo=nombre_archivo_seguro(archivo.name),
                                                  ruta_objeto=ruta_objeto, hash_sha256=huella, subida_por=usuario)
    registrar(usuario, "creacion", "evidencia_actividad", evidencia.pk, detalle="sha256 %s" % huella)
    return evidencia


def leer_evidencia(evidencia):
    return almacenamiento.leer_bytes(evidencia.ruta_objeto, evidencia.hash_sha256)


# ---------------------------------------------------------------------------------------------- indicadores
def indicadores_bienestar(anio, hoy=None):
    """Seis indicadores de la pantalla «Indicadores de bienestar». Todas son cifras agregadas.

    Índice de bienestar (definición propuesta, a validar con el equipo): proporción de estudiantes activos del año que
    NO presentan ninguna señal de riesgo — caso con urgencia alta sin cerrar, alerta de riesgo del año, falta gravísima
    del año o inasistencia grave o crítica (menos de 85 %) registrada en el año.
    """
    from apps.alertas.models import AlertaRiesgo
    from apps.casos.models import Caso
    from apps.casos.servicios import casos_urgentes
    from apps.estudiantes.models import Estudiante

    from .models import Anotacion, RegistroConductual

    hoy = hoy or timezone.localdate()
    activos = Estudiante.objects.filter(curso__anio_escolar=anio).exclude(tipo_salida="egreso").activos()
    total = activos.count()
    en_riesgo = set(casos_urgentes(Caso.objects.filter(estudiante__in=activos)).values_list("estudiante_id", flat=True))
    en_riesgo |= set(AlertaRiesgo.objects.filter(estudiante__in=activos, fecha_hora_registro__year=anio)
                     .values_list("estudiante_id", flat=True))
    en_riesgo |= set(Anotacion.objects.filter(estudiante__in=activos, tipo="gravisima", fecha__year=anio)
                     .values_list("estudiante_id", flat=True))
    en_riesgo |= set(RegistroConductual.objects.filter(estudiante__in=activos, categoria="asistencia", fecha__year=anio,
                                                       porcentaje_asistencia__lt=85).values_list("estudiante_id", flat=True))
    casos = Caso.objects.filter(fecha_apertura__year__lte=anio)
    abiertos = casos.exclude(estado="cerrado").count()
    mes = hoy.month if anio == hoy.year else 12
    resueltos_mes = Caso.objects.filter(estado="cerrado", fecha_cierre__year=anio, fecha_cierre__month=mes).count()
    abiertos_anio = Caso.objects.filter(fecha_apertura__year=anio).count()
    cerrados_anio = Caso.objects.filter(fecha_apertura__year=anio, estado="cerrado").count()
    return {
        "indice": 100 * (total - len(en_riesgo)) / total if total else None, "total_activos": total,
        "con_senales": len(en_riesgo),
        "casos_activos": abiertos, "resueltos_mes": resueltos_mes, "mes": mes,
        "en_seguimiento": Caso.objects.exclude(estado="cerrado").values("estudiante").distinct().count(),
        "alertas_pendientes": AlertaRiesgo.objects.filter(estado="registrada").count(),
        "tasa_resolucion": 100 * cerrados_anio / abiertos_anio if abiertos_anio else None,
        "abiertos_anio": abiertos_anio, "cerrados_anio": cerrados_anio,
    }
