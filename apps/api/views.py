"""API REST mínima (Django REST Framework) que usan el panel analítico y la línea de tiempo del caso.
Aplica las mismas reglas de acceso y de auditoría que las vistas HTML."""
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from apps.auditoria.servicios import registrar
from apps.casos.acceso import puede_ver_caso
from apps.casos.models import Caso
from apps.casos.servicios import linea_de_tiempo
from apps.reportes.servicios import resumen


def requiere(*codigos):
    class _Permiso(BasePermission):
        message = "No tiene permiso para este recurso."

        def has_permission(self, request, view):
            return request.user.is_authenticated and request.user.tiene_permiso(*codigos)
    return _Permiso


@api_view(["GET"])
@permission_classes([IsAuthenticated, requiere("reportes.ver")])
def resumen_reportes(request):
    return Response(resumen())


@api_view(["GET"])
@permission_classes([IsAuthenticated, requiere("caso.ver_equipo", "caso.ver_pie")])
def linea_tiempo(request, pk):
    caso = get_object_or_404(Caso, pk=pk)
    if not puede_ver_caso(request.user, caso):
        registrar(request.user, "acceso_denegado", "caso", caso.pk, detalle="api linea de tiempo")
        return Response({"detalle": "No tiene acceso a este caso."}, status=403)
    registrar(request.user, "consulta", "caso", caso.pk, detalle="api linea de tiempo")
    items = [{**{k: v for k, v in i.items() if k != "fecha"}, "fecha": i["fecha"].isoformat()}
             for i in linea_de_tiempo(caso, request.user)]
    return Response({"caso": caso.pk, "items": items})
