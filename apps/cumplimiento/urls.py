from django.urls import path

from . import views

app_name = "cumplimiento"

urlpatterns = [
    path("consentimientos/estudiante/<int:estudiante_pk>/nuevo/", views.consentimiento_nuevo, name="consentimiento_nuevo"),
    path("consentimientos/<int:pk>/revocar/", views.consentimiento_revocar, name="consentimiento_revocar"),
    path("arco/", views.arco_lista, name="arco"),
    path("arco/estudiante/<int:estudiante_pk>/nueva/", views.arco_nueva, name="arco_nueva"),
    path("arco/<int:pk>/", views.arco_detalle, name="arco_detalle"),
    path("arco/nueva/", views.arco_buscar, name="arco_buscar"),
    path("arco/<int:pk>/exportar/", views.arco_exportar, name="arco_exportar"),
    path("arco/<int:pk>/analizar/", views.arco_analizar, name="arco_analizar"),
    path("arco/<int:pk>/acceso/", views.arco_informe_acceso, name="arco_acceso"),
    path("arco/<int:pk>/rectificar/", views.arco_rectificar, name="arco_rectificar"),
    path("arco/<int:pk>/suprimir/", views.arco_suprimir, name="arco_suprimir"),
    path("arco/<int:pk>/oponerse/", views.arco_oponerse, name="arco_oponerse"),
    path("arco/<int:pk>/bloquear/", views.arco_bloquear, name="arco_bloquear"),
    path("arco/<int:pk>/desbloquear/", views.arco_desbloquear, name="arco_desbloquear"),
    path("arco/<int:pk>/carta/", views.arco_carta, name="arco_carta"),
    path("retenciones/", views.retenciones, name="retenciones"),
    path("retenciones/<int:pk>/decidir/", views.retencion_decidir, name="retencion_decidir"),
]
