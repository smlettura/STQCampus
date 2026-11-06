import datetime

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.validadores import inicio_del_dia
from apps.cuentas.permisos import permiso_requerido

from .models import EventoAuditoria
from .servicios import registrar, verificar_cadena


@permiso_requerido("bitacora.ver")
def bitacora(request):
    """RF-10: quién consultó, modificó o exportó información sensible, y cuándo."""
    qs = EventoAuditoria.objects.select_related("usuario")
    accion = request.GET.get("accion")
    if accion in dict(EventoAuditoria.ACCIONES):
        qs = qs.filter(accion=accion)
    entidad = request.GET.get("entidad", "").strip()
    if entidad:
        qs = qs.filter(entidad=entidad)
    if request.GET.get("id_entidad", "").isdigit():
        qs = qs.filter(id_entidad=int(request.GET["id_entidad"]))
    usuario = request.GET.get("usuario", "").strip()
    if usuario:
        qs = qs.filter(usuario__correo__icontains=usuario)
    try:
        qs = qs.filter(fecha_hora__gte=inicio_del_dia(datetime.date.fromisoformat(request.GET.get("desde", ""))))
    except ValueError:
        pass
    try:
        hasta = datetime.date.fromisoformat(request.GET.get("hasta", "")) + datetime.timedelta(days=1)
        qs = qs.filter(fecha_hora__lt=inicio_del_dia(hasta))
    except ValueError:
        pass
    pagina = Paginator(qs, 50).get_page(request.GET.get("pagina"))
    registrar(request.user, "consulta", "bitacora", None)
    entidades = EventoAuditoria.objects.order_by().values_list("entidad", flat=True).distinct()
    return render(request, "auditoria/bitacora.html", {"pagina": pagina, "acciones": EventoAuditoria.ACCIONES,
                                                       "entidades": sorted(set(entidades)), "filtros": request.GET})


@require_POST
@permiso_requerido("bitacora.ver")
def verificar(request):
    integra, id_roto, total = verificar_cadena()
    registrar(request.user, "consulta", "bitacora", None, detalle="verificación de integridad")
    if integra:
        messages.success(request, "Cadena íntegra: %d eventos verificados, ninguno alterado." % total)
    else:
        messages.error(request, "¡Atención! La cadena se rompe en el evento %d: la bitácora fue alterada fuera de la "
                                "aplicación." % id_roto)
    return redirect("auditoria:bitacora")
