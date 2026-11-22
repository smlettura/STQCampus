"""Ejecución de los derechos ARCO+ (Ley 21.719): acceso, rectificación, supresión, oposición, portabilidad y bloqueo.

Cada acción queda en el historial de la solicitud (AccionARCO) y en la bitácora de auditoría, sin datos personales:
solo se registra qué campos cambiaron o qué alcance se revocó, nunca los valores.
"""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.auditoria.servicios import registrar

from .models import AccionARCO, BloqueoTratamiento, Consentimiento, RetencionEliminacion

PENDIENTES = ("recibida", "en_analisis")
# Qué acciones corresponden a cada derecho. El bloqueo temporal también procede mientras se resuelve una
# rectificación, una oposición o una supresión.
ACCIONES_POR_DERECHO = {
    "acceso": {"exportar", "informe_acceso"},
    "portabilidad": {"exportar"},
    "rectificacion": {"rectificar", "bloquear"},
    "supresion": {"suprimir", "bloquear"},
    "oposicion": {"oponerse", "bloquear"},
    "bloqueo": {"bloquear"},
}


def puede(solicitud, accion):
    return accion in ACCIONES_POR_DERECHO.get(solicitud.tipo_derecho, set())


def anotar(solicitud, usuario, tipo, detalle=""):
    return AccionARCO.objects.create(solicitud=solicitud, usuario=usuario, tipo=tipo, detalle=detalle[:255])


def _exigir_pendiente(solicitud):
    if solicitud.estado not in PENDIENTES:
        raise ValidationError("La solicitud ya fue cerrada (%s)." % solicitud.get_estado_display().lower())


@transaction.atomic
def iniciar_analisis(solicitud, usuario):
    if solicitud.estado == "recibida":
        solicitud.estado = "en_analisis"
        solicitud.save(update_fields=["estado"])
        anotar(solicitud, usuario, "analisis")
        registrar(usuario, "modificacion", "solicitud_arco", solicitud.pk, detalle="en análisis")


def _pasar_a_analisis(solicitud, usuario):
    if solicitud.estado == "recibida":
        iniciar_analisis(solicitud, usuario)


@transaction.atomic
def rectificar(solicitud, usuario, form_estudiante, form_apoderado=None):
    """Aplica la corrección. Devuelve la lista de campos modificados (solo nombres de campo)."""
    _exigir_pendiente(solicitud)
    cambiados = ["estudiante.%s" % c for c in form_estudiante.changed_data]
    if form_estudiante.changed_data:
        form_estudiante.save()
    if form_apoderado is not None and form_apoderado.changed_data:
        cambiados += ["apoderado.%s" % c for c in form_apoderado.changed_data]
        form_apoderado.save()
    if not cambiados:
        raise ValidationError("No hay cambios que aplicar.")
    _pasar_a_analisis(solicitud, usuario)
    detalle = "campos: %s" % ", ".join(cambiados)
    anotar(solicitud, usuario, "rectificacion", detalle)
    registrar(usuario, "modificacion", "estudiante", solicitud.estudiante_id, detalle="rectificación ARCO+ %d; %s" % (solicitud.pk, detalle))
    return cambiados


@transaction.atomic
def proponer_supresion(solicitud, usuario, accion):
    """La supresión no se ejecuta aquí: se propone a la Directora, que la autoriza en «Retención» (la ley obliga a
    conservar ciertos registros, por lo que la decisión final es de la responsable del tratamiento)."""
    _exigir_pendiente(solicitud)
    existente = RetencionEliminacion.objects.filter(estudiante=solicitud.estudiante,
                                                    estado__in=["propuesta", "autorizada"]).first()
    if existente:
        raise ValidationError("Ya hay una eliminación o anonimización en curso para este expediente.")
    r = RetencionEliminacion.objects.create(estudiante=solicitud.estudiante, fecha_vencimiento=timezone.localdate(),
                                            accion=accion, origen="arco", solicitud_arco=solicitud)
    _pasar_a_analisis(solicitud, usuario)
    anotar(solicitud, usuario, "supresion", "acción propuesta: %s" % accion)
    registrar(usuario, "creacion", "retencion_eliminacion", r.pk, detalle="supresión ARCO+ %d" % solicitud.pk)
    return r


@transaction.atomic
def oponerse(solicitud, usuario, alcances):
    """Oposición: revoca hoy los consentimientos vigentes de los alcances indicados."""
    _exigir_pendiente(solicitud)
    hoy = timezone.localdate()
    vigentes = [c for c in solicitud.estudiante.consentimientos.filter(alcance__in=alcances, fecha_revocacion__isnull=True)]
    if not vigentes:
        raise ValidationError("No hay consentimientos vigentes con esos alcances.")
    for c in vigentes:
        c.fecha_revocacion = hoy
        c.full_clean()
        c.save(update_fields=["fecha_revocacion"])
        registrar(usuario, "modificacion", "consentimiento", c.pk, detalle="revocación por oposición ARCO+ %d" % solicitud.pk)
    _pasar_a_analisis(solicitud, usuario)
    anotar(solicitud, usuario, "oposicion", "alcances: %s" % ", ".join(sorted({c.alcance for c in vigentes})))
    return vigentes


@transaction.atomic
def bloquear(solicitud, usuario, motivo):
    _exigir_pendiente(solicitud)
    if BloqueoTratamiento.activo_para(solicitud.estudiante):
        raise ValidationError("El tratamiento de este estudiante ya está bloqueado.")
    b = BloqueoTratamiento.objects.create(estudiante=solicitud.estudiante, solicitud=solicitud, motivo=motivo,
                                          creado_por=usuario)
    _pasar_a_analisis(solicitud, usuario)
    anotar(solicitud, usuario, "bloqueo")
    registrar(usuario, "creacion", "bloqueo_tratamiento", b.pk, detalle="ARCO+ %d" % solicitud.pk)
    return b


@transaction.atomic
def desbloquear(solicitud, usuario):
    vigentes = BloqueoTratamiento.objects.filter(estudiante=solicitud.estudiante, fecha_termino__isnull=True)
    if not vigentes.exists():
        raise ValidationError("No hay un bloqueo vigente.")
    for b in vigentes:
        b.fecha_termino = timezone.now()
        b.save(update_fields=["fecha_termino"])
        registrar(usuario, "modificacion", "bloqueo_tratamiento", b.pk, detalle="bloqueo levantado")
    anotar(solicitud, usuario, "desbloqueo")


def registrar_exportacion(solicitud, usuario, tipo="exportacion"):
    _pasar_a_analisis(solicitud, usuario)
    anotar(solicitud, usuario, tipo)


@transaction.atomic
def responder(solicitud, usuario, form):
    form.save()
    anotar(solicitud, usuario, "respuesta", "estado: %s" % solicitud.estado)
    registrar(usuario, "modificacion", "solicitud_arco", solicitud.pk, detalle=solicitud.estado)
