from django.urls import path

from . import views

app_name = "alertas"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("registrar/", views.registrar_alerta, name="registrar"),
    path("constancias/", views.constancias, name="constancias"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/constancia/", views.constancia_registro, name="constancia_registro"),
    path("<int:pk>/gestionar/", views.gestionar, name="gestionar"),
    path("<int:pk>/denunciar/", views.denunciar, name="denunciar"),
    path("<int:pk>/vincular-caso/", views.vincular_caso, name="vincular_caso"),
]
