from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    path("reportes/resumen/", views.resumen_reportes, name="resumen"),
    path("casos/<int:pk>/linea-tiempo/", views.linea_tiempo, name="linea_tiempo"),
]
