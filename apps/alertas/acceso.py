"""Acceso restringido al flujo de alertas (RF-13): solo quien reporta, quienes el reglamento designa y quienes custodian
las constancias (Directora y psicóloga designada para denunciar)."""
from django.db.models import Q

from .models import AlertaRiesgo


def alertas_visibles(usuario):
    if usuario.tiene_permiso("alerta.ver_constancias"):
        return AlertaRiesgo.objects.all()
    return AlertaRiesgo.objects.filter(Q(notificaciones__destinatario=usuario) | Q(informante=usuario)).distinct()


def es_destinatario(usuario, alerta):
    return alerta.notificaciones.filter(destinatario=usuario).exists()


def puede_ver(usuario, alerta):
    return alertas_visibles(usuario).filter(pk=alerta.pk).exists()


def puede_gestionar(usuario, alerta):
    return usuario.tiene_permiso("alerta.gestionar") and (
        es_destinatario(usuario, alerta) or usuario.tiene_permiso("alerta.ver_constancias"))
