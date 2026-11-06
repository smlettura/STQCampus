from django.urls import path

from . import views

app_name = "cumplimiento"

urlpatterns = [
    path("consentimientos/estudiante/<int:estudiante_pk>/nuevo/", views.consentimiento_nuevo, name="consentimiento_nuevo"),
    path("consentimientos/<int:pk>/revocar/", views.consentimiento_revocar, name="consentimiento_revocar"),
    path("arco/", views.arco_lista, name="arco"),
    path("arco/estudiante/<int:estudiante_pk>/nueva/", views.arco_nueva, name="arco_nueva"),
    path("arco/<int:pk>/", views.arco_detalle, name="arco_detalle"),
    path("arco/<int:pk>/exportar/", views.arco_exportar, name="arco_exportar"),
    path("retenciones/", views.retenciones, name="retenciones"),
    path("retenciones/<int:pk>/decidir/", views.retencion_decidir, name="retencion_decidir"),
]
