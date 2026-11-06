from django.urls import path

from . import views

app_name = "evaluacion"

urlpatterns = [
    path("caso/<int:caso_pk>/nueva/", views.evaluacion_nueva, name="nueva"),
    path("<int:pk>/", views.evaluacion_detalle, name="detalle"),
    path("<int:pk>/editar/", views.evaluacion_editar, name="editar"),
    path("<int:pk>/participacion/", views.participacion_nueva, name="participacion"),
    path("<int:pk>/cerrar/", views.evaluacion_cerrar, name="cerrar"),
    path("planes/estudiante/<int:estudiante_pk>/nuevo/", views.plan_nuevo, name="plan_nuevo"),
    path("planes/<int:pk>/editar/", views.plan_editar, name="plan_editar"),
    path("planes/<int:pk>/cerrar/", views.plan_cerrar, name="plan_cerrar"),
    path("informes/caso/<int:caso_pk>/nuevo/", views.informe_nuevo, name="informe_nuevo"),
    path("informes/<int:pk>/", views.informe_detalle, name="informe"),
    path("informes/<int:pk>/editar/", views.informe_editar, name="informe_editar"),
    path("informes/<int:pk>/validar/", views.informe_validar, name="informe_validar"),
    path("informes/<int:pk>/entregar/", views.informe_entregar, name="informe_entregar"),
    path("informes/<int:pk>/descartar/", views.informe_descartar, name="informe_descartar"),
    path("avisos/", views.avisos, name="avisos"),
]
