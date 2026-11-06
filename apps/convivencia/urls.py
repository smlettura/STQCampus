from django.urls import path

from . import views

app_name = "convivencia"

urlpatterns = [
    path("conflictos/", views.conflictos, name="conflictos"),
    path("conflictos/nuevo/", views.conflicto_form, name="conflicto_nuevo"),
    path("conflictos/<int:pk>/", views.conflicto_detalle, name="conflicto"),
    path("conflictos/<int:pk>/editar/", views.conflicto_form, name="conflicto_editar"),
    path("anotaciones/", views.anotaciones, name="anotaciones"),
    path("anotaciones/nueva/", views.anotacion_nueva, name="anotacion_nueva"),
    path("situacion/", views.situacion, name="situacion"),
    path("situacion/detalle/", views.situacion_detalle, name="situacion_detalle"),
    path("situacion/descargar/", views.situacion_descargar, name="situacion_descargar"),
    path("situacion/nuevo/", views.registro_nuevo, name="registro_nuevo"),
    path("protocolos/", views.protocolos, name="protocolos"),
    path("protocolos/nuevo/", views.protocolo_nuevo, name="protocolo_nuevo"),
    path("protocolos/<int:pk>/", views.protocolo_detalle, name="protocolo"),
    path("plan/", views.plan, name="plan"),
    path("plan/descargar/", views.plan_descargar, name="plan_descargar"),
    path("plan/nueva/", views.actividad_form, name="actividad_nueva"),
    path("plan/<int:pk>/", views.actividad_detalle, name="actividad"),
    path("plan/<int:pk>/editar/", views.actividad_form, name="actividad_editar"),
    path("plan/evidencias/<int:pk>/descargar/", views.evidencia_descargar, name="evidencia"),
    path("indicadores/", views.indicadores, name="indicadores"),
]
