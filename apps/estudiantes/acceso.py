"""Reglas de acceso a nivel de objeto para fichas de estudiantes."""
from django.utils import timezone

from .models import Estudiante


def estudiantes_visibles(usuario):
    if usuario.tiene_permiso("estudiante.ver_todos"):
        return Estudiante.objects.all()
    if usuario.tiene_permiso("estudiante.ver_curso"):
        # El profesor jefe solo ve a los estudiantes de sus cursos del año escolar vigente.
        return Estudiante.objects.filter(curso__profesor_jefe=usuario, curso__anio_escolar=timezone.localdate().year)
    return Estudiante.objects.none()


def puede_ver_estudiante(usuario, estudiante):
    return estudiantes_visibles(usuario).filter(pk=estudiante.pk).exists()


def es_profesor_jefe_de(usuario, estudiante):
    return estudiante.curso.profesor_jefe_id == usuario.pk and usuario.tiene_permiso("estudiante.ver_curso")
