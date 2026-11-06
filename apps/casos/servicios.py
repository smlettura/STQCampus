"""Vista cronológica del caso (RF-03): sesiones, hitos, documentos, evaluaciones y derivaciones en una sola línea de tiempo."""
import datetime

from django.db.models import OuterRef, Q, Subquery
from django.utils import timezone

from .acceso import puede_ver_notas, sesiones_visibles
from .models import Caso, SesionSeguimiento


def con_ultima_urgencia(casos):
    """Anota en cada caso la urgencia de su última atención registrada."""
    ultima = (SesionSeguimiento.objects.filter(caso=OuterRef("pk"), estado="registrada")
              .order_by("-fecha_hora").values("urgencia")[:1])
    return casos.annotate(ultima_urgencia=Subquery(ultima))


def casos_urgentes(casos=None):
    """Casos sin cerrar cuya última atención se registró con urgencia alta («Casos urgentes» del prototipo)."""
    casos = Caso.objects.all() if casos is None else casos
    return con_ultima_urgencia(casos.exclude(estado="cerrado")).filter(ultima_urgencia="alta")


def atenciones_previas(estudiante, usuario, limite=6):
    """Atenciones anteriores del estudiante que la usuaria puede ver (panel lateral de «Registrar atención»)."""
    return (SesionSeguimiento.objects.filter(caso__estudiante=estudiante)
            .filter(Q(estado="registrada", nivel_acceso="equipo") | Q(profesional=usuario))
            .select_related("caso").order_by("-fecha_hora")[:limite])


def _como_fecha_hora(valor):
    if isinstance(valor, datetime.datetime):
        return timezone.localtime(valor)
    return timezone.make_aware(datetime.datetime.combine(valor, datetime.time(0, 0)))


def linea_de_tiempo(caso, usuario):
    items = []
    ve_notas = puede_ver_notas(usuario, caso)
    for s in sesiones_visibles(usuario, caso):
        if s.estado == "borrador" and s.profesional_id != usuario.pk:
            continue                      # los borradores solo los ve su autora
        texto = s.nota
        if s.acuerdos:
            texto = "%s\n\nAcuerdos y compromisos: %s" % (texto, s.acuerdos)
        items.append({"tipo": "sesion", "etiqueta": s.titulo, "fecha": _como_fecha_hora(s.fecha_hora), "con_hora": True,
                      "autor": s.profesional.nombre_completo, "texto": texto or "(sin descripción)",
                      "privada": s.nivel_acceso == "autora", "borrador": s.estado == "borrador", "id": s.pk,
                      "detalle": "%s · %d min · urgencia %s" % (s.get_motivo_display(), s.duracion_minutos,
                                                                  s.get_urgencia_display().lower()),
                      "urgente": s.urgencia == "alta"})
    hitos = caso.hitos.all() if ve_notas else caso.hitos.filter(visible_profesor_jefe=True)
    for h in hitos:
        items.append({"tipo": "hito", "etiqueta": h.get_tipo_display(), "fecha": _como_fecha_hora(h.fecha),
                      "con_hora": False, "texto": h.descripcion, "visible_pj": h.visible_profesor_jefe})
    for d in caso.documentos.all():
        items.append({"tipo": "documento", "etiqueta": "Documento: " + d.get_tipo_display(),
                      "fecha": _como_fecha_hora(d.fecha_carga), "con_hora": True, "texto": d.nombre_archivo, "id": d.pk})
    for ev in caso.evaluaciones.all():
        items.append({"tipo": "evaluacion", "etiqueta": "Evaluación diagnóstica (%s)" % ev.get_tipo_evaluacion_display().lower(),
                      "fecha": _como_fecha_hora(ev.fecha_evaluacion), "con_hora": False,
                      "texto": "%s · %s" % (ev.tipo_nee, ev.get_estado_display()), "id": ev.pk})
    for der in caso.derivaciones.select_related("derivante"):
        items.append({"tipo": "derivacion", "etiqueta": "Derivación", "fecha": _como_fecha_hora(der.fecha_hora),
                      "con_hora": True, "autor": der.derivante.nombre_completo,
                      "texto": der.motivo if ve_notas else "Motivo reservado al equipo psicosocial."})
    items.sort(key=lambda i: i["fecha"], reverse=True)
    return items
