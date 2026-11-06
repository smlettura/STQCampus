"""Enrutamiento de alertas según el reglamento interno, constancias con hash y registro de la denuncia."""
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.auditoria.servicios import registrar
from apps.core.avisos import enviar_aviso
from apps.cuentas.models import Usuario

from .models import Notificacion, ReglaEnrutamiento


def reglas_aplicables(alerta):
    reglas = ReglaEnrutamiento.objects.filter(vigente=True, tipo_situacion=alerta.tipo_situacion)
    reglas = reglas.filter(Q(sede__isnull=True) | Q(sede_id=alerta.sede_id))
    if alerta.tipo_situacion == "violencia_maltrato":
        reglas = reglas.filter(subtipo_violencia=alerta.subtipo_violencia)
    return reglas.select_related("rol_responsable")


def responsables(alerta):
    """Usuarios activos con el rol responsable, vigente y válido para la sede de la alerta."""
    hoy = timezone.localdate()
    roles = [r.rol_responsable_id for r in reglas_aplicables(alerta)]
    usuarios = Usuario.objects.filter(activo=True, asignaciones__rol_id__in=roles, asignaciones__vigente_desde__lte=hoy)
    usuarios = usuarios.filter(Q(asignaciones__vigente_hasta__isnull=True) | Q(asignaciones__vigente_hasta__gte=hoy))
    usuarios = usuarios.filter(Q(asignaciones__sede__isnull=True) | Q(asignaciones__sede_id=alerta.sede_id))
    return usuarios.exclude(pk=alerta.informante_id).distinct()


def usuarios_con_rol(codigo):
    hoy = timezone.localdate()
    return Usuario.objects.filter(activo=True, asignaciones__rol__codigo=codigo, asignaciones__vigente_desde__lte=hoy).filter(
        Q(asignaciones__vigente_hasta__isnull=True) | Q(asignaciones__vigente_hasta__gte=hoy)).distinct()


def _crear_notificacion(alerta, usuario, canal):
    n = Notificacion(alerta=alerta, destinatario=usuario, canal=canal, fecha_hora_envio=timezone.now())
    n.hash_constancia = n.calcular_hash()
    n.save()
    registrar(None, "creacion", "notificacion", n.pk, detalle="constancia %s" % n.hash_constancia)
    return n


@transaction.atomic
def notificar_alerta(alerta):
    """Crea las notificaciones (plataforma y correo) para los responsables que designa el reglamento.
    Si ninguna regla aplica, o no hay usuarios con ese rol, se notifica a la Directora."""
    destinatarios = list(responsables(alerta))
    sin_responsable = not destinatarios
    if sin_responsable:
        destinatarios = list(usuarios_con_rol("directora").exclude(pk=alerta.informante_id))
    ruta = reverse("alertas:detalle", args=[alerta.pk])
    creadas = []
    for usuario in destinatarios:
        creadas.append(_crear_notificacion(alerta, usuario, "plataforma"))
        transaction.on_commit(lambda u=usuario: enviar_aviso(u, "Nueva alerta de riesgo asignada", ruta))
        creadas.append(_crear_notificacion(alerta, usuario, "correo"))
    return creadas, sin_responsable


@transaction.atomic
def registrar_denuncia(denuncia):
    """Sella la constancia, informa a la Directora y marca la alerta como denunciada."""
    denuncia.directora_informada_en = timezone.now()
    denuncia.hash_constancia = denuncia.calcular_hash()
    denuncia.save()
    alerta = denuncia.alerta
    alerta.posible_delito = True
    alerta.estado = "denunciada"
    alerta.save(update_fields=["posible_delito", "estado"])
    registrar(denuncia.psicologa, "creacion", "denuncia", denuncia.pk, detalle="constancia %s" % denuncia.hash_constancia)
    ruta = reverse("alertas:detalle", args=[alerta.pk])
    for directora in usuarios_con_rol("directora"):
        _crear_notificacion(alerta, directora, "plataforma")
        _crear_notificacion(alerta, directora, "correo")
        transaction.on_commit(lambda u=directora: enviar_aviso(u, "Se registró una denuncia", ruta))
    return denuncia
