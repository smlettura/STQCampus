"""Menú lateral del diseño «panel analítico»: grupos con ícono y subenlaces según los permisos del rol.

Cada enlace declara los prefijos de ruta que lo marcan como activo; gana el prefijo más largo, de modo que por ejemplo
`/casos/derivaciones/` activa «Derivaciones» y no «Casos». El grupo activo se muestra desplegado.
"""
from django.urls import reverse

# (clave, nombre, ícono, [(nombre de url, texto, permisos (cualquiera), prefijos, opciones)])
# El orden y los nombres siguen el prototipo v1: Atención psicosocial, Estudiantes, Convivencia, Protocolos, Plan de gestión
# e Indicadores; luego los módulos de los requisitos que el prototipo no dibujó (alertas, cumplimiento, administración).
_EQUIPO = ("caso.ver_equipo", "caso.ver_pie")
GRUPOS = [
    ("atencion", "Atención psicosocial", "atencion", [
        ("casos:resumen", "Resumen", _EQUIPO + ("reportes.ver",), ("=/", "/casos/resumen/"), {}),
        ("casos:registrar_atencion", "Registrar atención", ("caso.gestionar",), ("/casos/atencion/",), {}),
        ("casos:lista", "Fichas de estudiantes", _EQUIPO,
         ("/casos/", "/evaluacion/", "/cumplimiento/consentimientos/"), {}),
        ("casos:derivaciones", "Derivaciones", ("caso.gestionar",), ("/casos/derivaciones/",), {}),
        ("evaluacion:avisos", "Avisos de reevaluación", ("evaluacion.gestionar",), ("/evaluacion/avisos/",), {}),
        ("ia:generar_informe", "Generar informe (IA)", ("ia.usar",), ("/ia/",), {}),
        ("reportes:panel", "Estadísticas", ("reportes.ver",), ("/reportes/",), {}),
        ("casos:derivar", "Derivar al equipo", ("caso.derivar",), ("/casos/derivar/",), {}),
    ]),
    ("estudiantes", "Estudiantes", "estudiantes", [
        ("estudiantes:lista", "Lista de estudiantes", ("estudiante.ver_todos", "estudiante.ver_curso"),
         ("/estudiantes/", "/evaluacion/planes/"), {}),
        ("estudiantes:crear", "Registrar estudiante", ("estudiante.gestionar",),
         ("/estudiantes/nuevo/", "/estudiantes/importar/"), {}),
        ("estudiantes:cursos", "Cursos", ("estudiante.ver_todos", "curso.gestionar"), ("/estudiantes/cursos/",), {}),
        ("estudiantes:promocion", "Promoción", ("promocion.gestionar",), ("/estudiantes/promocion/",), {}),
        ("estudiantes:egresados", "Egresados", ("estudiante.ver_todos",), ("/estudiantes/egresados/",), {}),
    ]),
    ("convivencia", "Convivencia", "convivencia", [
        ("convivencia:conflictos", "Conflictos", ("convivencia.ver",), ("/convivencia/conflictos/",), {}),
        ("convivencia:anotaciones", "Anotaciones", ("convivencia.ver", "anotacion.registrar"),
         ("/convivencia/anotaciones/",), {}),
        ("convivencia:situacion", "Situación conductual", ("convivencia.ver",), ("/convivencia/situacion/",), {}),
    ]),
    ("protocolos", "Protocolos", "protocolos", [
        ("convivencia:protocolos", "Protocolos", ("protocolo.ver", "protocolo.gestionar"), ("/convivencia/protocolos/",), {}),
    ]),
    ("plan", "Plan de gestión", "plan", [
        ("convivencia:plan", "Plan de gestión", ("plan_convivencia.ver", "plan_convivencia.gestionar"),
         ("/convivencia/plan/",), {}),
    ]),
    ("indicadores", "Indicadores", "indicadores", [
        ("convivencia:indicadores", "Indicadores", ("reportes.ver",), ("/convivencia/indicadores/",), {}),
    ]),
    ("alertas", "Alertas de riesgo", "alertas", [
        ("alertas:lista", "Alertas", ("alerta.registrar", "alerta.gestionar", "alerta.ver_constancias"),
         ("/alertas/",), {"contador": True}),
        ("alertas:constancias", "Constancias", ("alerta.ver_constancias",), ("/alertas/constancias/",), {}),
        ("alertas:registrar", "Registrar alerta", ("alerta.registrar",), ("/alertas/registrar/",), {"urgente": True}),
    ]),
    ("gestion", "Cumplimiento", "gestion", [
        ("cumplimiento:arco", "Solicitudes ARCO+", ("arco.gestionar",), ("/cumplimiento/arco/",), {}),
        ("cumplimiento:retenciones", "Retención (15 años)", ("retencion.ver",), ("/cumplimiento/retenciones/",), {}),
    ]),
    ("admin", "Administración", "admin", [
        ("cuentas:usuarios", "Usuarios y roles", ("usuarios.administrar",), ("/cuentas/usuarios/", "/cuentas/asignaciones/"), {}),
        ("auditoria:bitacora", "Bitácora de auditoría", ("bitacora.ver",), ("/bitacora/",), {}),
    ]),
]


def _coincidencia(ruta, prefijos):
    mejor = -1
    for p in prefijos:
        if p.startswith("="):
            if ruta == p[1:]:
                mejor = max(mejor, 10_000)
        elif ruta.startswith(p):
            mejor = max(mejor, len(p))
    return mejor


def construir_menu(ruta, permisos, alertas_sin_leer=0):
    grupos, mejor, activo = [], -1, None
    for clave, nombre, icono, enlaces in GRUPOS:
        visibles = []
        for url, texto, requeridos, prefijos, opciones in enlaces:
            if requeridos and not any(p in permisos for p in requeridos):
                continue
            enlace = {"nombre": texto, "url": reverse(url), "activo": False, "urgente": opciones.get("urgente", False),
                      "contador": alertas_sin_leer if opciones.get("contador") else 0}
            puntaje = _coincidencia(ruta, prefijos)
            if puntaje > mejor:
                mejor, activo = puntaje, enlace
            visibles.append(enlace)
        if visibles:
            grupos.append({"clave": clave, "nombre": nombre, "icono": icono, "url": visibles[0]["url"],
                           "enlaces": visibles, "unico": len(visibles) == 1, "activo": False,
                           "contador": sum(e["contador"] for e in visibles)})
    if activo is not None:
        activo["activo"] = True
        for g in grupos:
            g["activo"] = any(e["activo"] for e in g["enlaces"])
    return grupos
