"""Rutas del agente del equipo propio (/ia/agente/*). Autenticación con token («Authorization: Bearer …»): la plataforma
guarda solo su hash SHA-256 y lo compara en la base. El token no sirve para iniciar sesión ni para consultar fichas.
La aplicación limita la tasa de estas rutas (sección 9.1.6 del informe)."""
import json

from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.auditoria.servicios import registrar

from . import servicios

LIMITE_POR_MINUTO = 30


def _agente(request):
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    return servicios.agente_por_token(token)


def ruta_agente(vista):
    @csrf_exempt
    @require_POST
    def envuelta(request, *args, **kwargs):
        agente = _agente(request)
        if agente is None:
            registrar(None, "acceso_denegado", "agente_ia", None, detalle="token inválido en %s" % request.path)
            return JsonResponse({"detalle": "Token inválido."}, status=401)
        clave = "ia_agente_tasa:%s:%s" % (agente.pk, timezone.now().strftime("%Y%m%d%H%M"))
        cache.add(clave, 0, 120)
        if cache.incr(clave) > LIMITE_POR_MINUTO:
            return JsonResponse({"detalle": "Demasiadas solicitudes; espere un minuto."}, status=429)
        try:
            datos = json.loads(request.body or b"{}")
        except ValueError:
            return JsonResponse({"detalle": "JSON inválido."}, status=400)
        return vista(request, agente, datos, *args, **kwargs)
    return envuelta


@ruta_agente
def latido(request, agente, datos):
    pendientes = servicios.latido(agente, str(datos.get("modelo", "")))
    return JsonResponse({"pendientes": pendientes})


@ruta_agente
def tomar(request, agente, datos):
    servicios.latido(agente, str(datos.get("modelo", "")))
    trabajo = servicios.tomar(agente)
    if trabajo is None:
        return HttpResponse(status=204)
    return JsonResponse(trabajo)


@ruta_agente
def resultado(request, agente, datos, pk):
    try:
        if datos.get("error"):
            servicios.registrar_error(agente, pk, str(datos["error"]))
        else:
            servicios.registrar_resultado(agente, pk, str(datos.get("texto", "")), str(datos.get("modelo", "")),
                                          datos.get("tokens_entrada", 0), datos.get("tokens_salida", 0))
    except servicios.ErrorSolicitud as e:
        return JsonResponse({"detalle": str(e)}, status=409)
    return JsonResponse({"ok": True})
