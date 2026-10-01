from django.urls import include, path

urlpatterns = [
    path("", include("apps.core.urls")),
    path("cuentas/", include("apps.cuentas.urls")),
    path("estudiantes/", include("apps.estudiantes.urls")),
    path("casos/", include("apps.casos.urls")),
    path("evaluacion/", include("apps.evaluacion.urls")),
    path("ia/", include("apps.ia.urls")),
    path("convivencia/", include("apps.convivencia.urls")),
    path("cumplimiento/", include("apps.cumplimiento.urls")),
    path("alertas/", include("apps.alertas.urls")),
    path("reportes/", include("apps.reportes.urls")),
    path("bitacora/", include("apps.auditoria.urls")),
    path("api/v1/", include("apps.api.urls")),
]

handler403 = "apps.core.views.error_403"
handler404 = "apps.core.views.error_404"
