from django.urls import path

from . import views

app_name = "casos"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("sugerencias/", views.sugerencias, name="sugerencias"),
    path("resumen/", views.resumen, name="resumen"),
    path("atencion/", views.registrar_atencion, name="registrar_atencion"),
    path("atencion/<int:pk>/descartar/", views.descartar_borrador, name="descartar_borrador"),
    path("nuevo/", views.nuevo, name="nuevo"),
    path("derivar/", views.derivar, name="derivar"),
    path("derivaciones/", views.derivaciones, name="derivaciones"),
    path("derivaciones/<int:pk>/abrir/", views.abrir_desde_derivacion, name="abrir"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/sesion/", views.sesion_nueva, name="sesion"),
    path("<int:pk>/hito/", views.hito_nuevo, name="hito"),
    path("<int:pk>/documento/", views.documento_subir, name="documento"),
    path("<int:pk>/cerrar/", views.cerrar, name="cerrar"),
    path("<int:pk>/reabrir/", views.reabrir, name="reabrir"),
    path("documentos/<int:pk>/descargar/", views.documento_descargar, name="descargar"),
]
