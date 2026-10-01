from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("tareas/<slug:nombre>/", views.tarea_programada, name="tarea_programada"),
]
