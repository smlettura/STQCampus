"""Datos base del sistema: sedes, permisos, roles y reglas de enrutamiento del reglamento interno. Es idempotente."""
from django.db import transaction

SEDES = [("Central", ""), ("Prebásica", ""), ("Básica", "")]

# Tabla «¿A quién reportar si sospecho o tengo certeza de una situación de riesgo?» del reglamento interno.
# (tipo, subtipo, sede o None = todas, rol responsable)
REGLAS = [
    ("vulneracion_derechos", "", None, "psicologa"),
    ("vulneracion_derechos", "", None, "asistente_social"),
    ("abuso_sexual", "", None, "encargada_convivencia"),
    ("alcohol_drogas_armas", "", None, "directora"),
    ("conducta_suicida", "", None, "psicologa"),
    ("violencia_maltrato", "entre_adultos", None, "directora"),
]
for _sub in ("entre_estudiantes", "estudiante_a_adulto", "adulto_a_estudiante"):
    REGLAS += [("violencia_maltrato", _sub, "Básica", "inspectoria"),
               ("violencia_maltrato", _sub, "Central", "encargada_convivencia"),
               ("violencia_maltrato", _sub, "Prebásica", "encargada_convivencia")]


@transaction.atomic
def inicializar_sistema():
    from apps.alertas.models import ReglaEnrutamiento
    from apps.core.models import Sede
    from apps.cuentas.models import Permiso, Rol, RolPermiso
    from apps.cuentas.permisos import PERMISOS, ROLES

    for codigo, descripcion in PERMISOS.items():
        Permiso.objects.update_or_create(codigo=codigo, defaults={"descripcion": descripcion})
    Permiso.objects.exclude(codigo__in=list(PERMISOS)).delete()      # permisos retirados del catálogo
    permisos = {p.codigo: p for p in Permiso.objects.all()}
    for codigo, (nombre, descripcion, codigos_permiso) in ROLES.items():
        rol, _ = Rol.objects.update_or_create(codigo=codigo, defaults={"nombre": nombre, "descripcion": descripcion})
        deseados = {permisos[c].pk for c in codigos_permiso}
        actuales = set(rol.rol_permisos.values_list("permiso_id", flat=True))
        RolPermiso.objects.filter(rol=rol, permiso_id__in=actuales - deseados).delete()
        RolPermiso.objects.bulk_create([RolPermiso(rol=rol, permiso_id=p) for p in deseados - actuales])
    for nombre, direccion in SEDES:
        Sede.objects.get_or_create(nombre=nombre, defaults={"direccion": direccion})
    roles = {r.codigo: r for r in Rol.objects.all()}
    sedes = {s.nombre: s for s in Sede.objects.all()}
    for tipo, subtipo, sede, rol in REGLAS:
        ReglaEnrutamiento.objects.get_or_create(tipo_situacion=tipo, subtipo_violencia=subtipo,
                                                sede=sedes[sede] if sede else None, rol_responsable=roles[rol],
                                                defaults={"vigente": True})
    return {"permisos": len(PERMISOS), "roles": len(ROLES), "sedes": len(SEDES), "reglas": len(REGLAS)}
