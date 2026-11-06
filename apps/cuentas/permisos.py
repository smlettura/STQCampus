"""Control de acceso basado en roles con mínimo privilegio (RF-09, RNF-02).

Las vistas declaran el permiso requerido; si el usuario no lo tiene se registra «acceso denegado» en la bitácora.
"""
from functools import wraps

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

# Catálogo de permisos: código -> descripción
PERMISOS = {
    "estudiante.ver_todos": "Ver la ficha de cualquier estudiante",
    "estudiante.ver_curso": "Ver la ficha de los estudiantes del curso a cargo (profesor jefe)",
    "estudiante.gestionar": "Crear y editar fichas de estudiantes y apoderados, y marcar retiros",
    "estudiante.importar": "Importar estudiantes desde Excel y exportar la nómina",
    "curso.gestionar": "Crear y editar cursos",
    "promocion.gestionar": "Procesar la promoción de fin de año (cursos terminales, repitentes y egresos)",
    "caso.derivar": "Derivar un estudiante al equipo psicosocial",
    "caso.gestionar": "Abrir, cerrar y registrar atenciones de casos",
    "caso.ver_equipo": "Ver los casos y notas del equipo psicosocial",
    "caso.ver_pie": "Ver casos PIE/NEE y TEA sin notas de sesión",
    "evaluacion.ver": "Ver evaluaciones diagnósticas",
    "evaluacion.gestionar": "Registrar evaluaciones diagnósticas integrales",
    "plan.ver": "Ver planes de apoyo completos",
    "plan.ver_adecuaciones": "Ver las adecuaciones de los planes de apoyo del curso a cargo",
    "plan.gestionar": "Registrar planes de apoyo (PACI, PAI, Decreto 67)",
    "informe.gestionar": "Elaborar informes (versión preliminar FUDEI, Informe para la Familia, seguimiento)",
    "ia.usar": "Usar el módulo de IA para informes (en configuración)",
    "convivencia.ver": "Ver conflictos, anotaciones y situación conductual",
    "convivencia.gestionar": "Registrar conflictos, mediaciones y situación conductual",
    "anotacion.registrar": "Registrar anotaciones (el profesor jefe, solo en su curso)",
    "protocolo.ver": "Ver los protocolos del reglamento activados",
    "protocolo.gestionar": "Activar y cerrar protocolos del reglamento interno",
    "plan_convivencia.ver": "Ver el plan de gestión de convivencia escolar",
    "plan_convivencia.gestionar": "Registrar actividades del plan de gestión y sus evidencias",
    "consentimiento.gestionar": "Registrar consentimientos informados",
    "arco.gestionar": "Atender solicitudes de derechos ARCO+",
    "retencion.ver": "Ver propuestas de eliminación por retención",
    "retencion.autorizar": "Autorizar eliminaciones por retención",
    "bitacora.ver": "Consultar la bitácora de auditoría",
    "usuarios.administrar": "Administrar usuarios, roles y permisos",
    "alerta.registrar": "Registrar alertas de riesgo",
    "alerta.gestionar": "Gestionar alertas asignadas y activar protocolos",
    "alerta.ver_constancias": "Consultar constancias de alertas y denuncias",
    "denuncia.registrar": "Registrar denuncias ante la autoridad",
    "reportes.ver": "Consultar estadísticas e indicadores agregados",
}

_CONVIVENCIA_LECTURA = ["convivencia.ver", "protocolo.ver", "plan_convivencia.ver"]
_PSICOSOCIAL = ["estudiante.ver_todos", "estudiante.gestionar", "estudiante.importar", "caso.derivar", "caso.gestionar",
                "caso.ver_equipo", "evaluacion.ver", "evaluacion.gestionar", "plan.ver", "informe.gestionar", "ia.usar",
                "consentimiento.gestionar", "arco.gestionar", "alerta.registrar", "alerta.gestionar", "reportes.ver",
                "protocolo.gestionar", "anotacion.registrar", *_CONVIVENCIA_LECTURA]
_CONVIVENCIA = ["estudiante.ver_todos", "alerta.registrar", "alerta.gestionar", "convivencia.gestionar",
                "anotacion.registrar", "protocolo.gestionar", "plan_convivencia.gestionar", "reportes.ver",
                *_CONVIVENCIA_LECTURA]

# Rol: (nombre, descripción, permisos)
ROLES = {
    "psicologa": ("Psicóloga", "Equipo psicosocial", _PSICOSOCIAL),
    "asistente_social": ("Asistente social", "Equipo psicosocial", _PSICOSOCIAL),
    "encargada_convivencia": ("Encargada de Convivencia", "Conflictos, anotaciones, protocolos y plan de gestión; recibe "
                              "reportes de abuso y de violencia según el reglamento", _CONVIVENCIA),
    "coordinacion_pie": ("Coordinación PIE", "Conduce la evaluación diagnóstica integral y los planes de apoyo",
                         ["estudiante.ver_todos", "estudiante.gestionar", "caso.ver_pie", "evaluacion.ver",
                          "evaluacion.gestionar", "plan.ver", "plan.gestionar", "informe.gestionar",
                          "consentimiento.gestionar", "alerta.registrar", "reportes.ver", "plan_convivencia.ver",
                          "plan_convivencia.gestionar"]),
    "profesor_jefe": ("Profesor jefe", "Ve la ficha básica, los hitos visibles y las adecuaciones de su curso",
                      ["estudiante.ver_curso", "plan.ver_adecuaciones", "caso.derivar", "alerta.registrar",
                       "anotacion.registrar"]),
    "inspectoria": ("Inspectoría de sede", "Deriva la inasistencia grave, registra la situación conductual y recibe "
                    "reportes de violencia (Sede Básica)",
                    ["estudiante.ver_todos", "caso.derivar", "alerta.registrar", "alerta.gestionar", "convivencia.ver",
                     "convivencia.gestionar", "anotacion.registrar", "protocolo.ver"]),
    "directora": ("Directora", "Autoridad del establecimiento",
                  ["estudiante.ver_todos", "alerta.registrar", "alerta.gestionar", "alerta.ver_constancias",
                   "retencion.ver", "retencion.autorizar", "bitacora.ver", "reportes.ver", *_CONVIVENCIA_LECTURA]),
    "administrador": ("Administrador", "Gestión de cuentas y datos maestros, sin acceso a contenido clínico",
                      ["usuarios.administrar", "curso.gestionar", "estudiante.ver_todos", "estudiante.gestionar",
                       "estudiante.importar", "promocion.gestionar", "arco.gestionar", "retencion.ver",
                       "bitacora.ver"]),
    "psicologa_denunciante": ("Psicóloga designada para denunciar", "Presenta y registra las denuncias",
                              ["denuncia.registrar", "alerta.ver_constancias"]),
    "funcionario": ("Funcionario", "Personal que puede derivar y reportar situaciones de riesgo",
                    ["caso.derivar", "alerta.registrar"]),
}

ROLES_PSICOSOCIALES = ("psicologa", "asistente_social")


def tiene_permiso(usuario, *codigos):
    return bool(usuario and usuario.is_authenticated and usuario.tiene_permiso(*codigos))


def _registrar_denegacion(request, detalle):
    from apps.auditoria.servicios import registrar
    registrar(request.user if request.user.is_authenticated else None, "acceso_denegado", "vista", None, detalle=detalle)


def denegar(request, detalle=""):
    _registrar_denegacion(request, detalle or request.path)
    raise PermissionDenied("No tiene permiso para realizar esta acción.")


class PermisoRequeridoMixin(LoginRequiredMixin):
    """Exige al menos uno de los permisos de `permiso_requerido` (cadena o tupla)."""

    permiso_requerido = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        codigos = (self.permiso_requerido,) if isinstance(self.permiso_requerido, str) else tuple(self.permiso_requerido)
        if codigos and not request.user.tiene_permiso(*codigos):
            denegar(request, "%s requiere %s" % (request.path, " o ".join(codigos)))
        return super().dispatch(request, *args, **kwargs)


def permiso_requerido(*codigos):
    def decorador(vista):
        @wraps(vista)
        def envuelta(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not request.user.tiene_permiso(*codigos):
                denegar(request, "%s requiere %s" % (request.path, " o ".join(codigos)))
            return vista(request, *args, **kwargs)
        return envuelta
    return decorador
