from django.urls import path

from . import views

app_name = "ia"

urlpatterns = [
    path("generar-informe/", views.generar_informe, name="generar_informe"),
]
