"""Reglas de acceso a nivel de objeto para casos y notas de sesión (RNF-02)."""
from django.db.models import Q

from .models import Caso, SesionSeguimiento

TIPOS_PIE = ("pie_nee", "tea")


def casos_visibles(usuario):
    if usuario.tiene_permiso("caso.ver_equipo"):
        return Caso.objects.all()
    if usuario.tiene_permiso("caso.ver_pie"):
        return Caso.objects.filter(tipo_proceso__in=TIPOS_PIE)
    return Caso.objects.none()


def puede_ver_caso(usuario, caso):
    return casos_visibles(usuario).filter(pk=caso.pk).exists()


def puede_ver_notas(usuario, caso):
    """Las notas de sesión son exclusivas del equipo psicosocial; la Coordinación PIE no las ve."""
    return usuario.tiene_permiso("caso.ver_equipo")


def puede_gestionar(usuario, caso):
    return usuario.tiene_permiso("caso.gestionar") and puede_ver_caso(usuario, caso)


def sesiones_visibles(usuario, caso):
    if not puede_ver_notas(usuario, caso):
        return SesionSeguimiento.objects.none()
    return caso.sesiones.filter(Q(nivel_acceso="equipo") | Q(profesional=usuario)).select_related("profesional")
