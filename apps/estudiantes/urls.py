from django.urls import path

from . import views

app_name = "estudiantes"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nuevo/", views.crear, name="crear"),
    path("exportar/", views.exportar, name="exportar"),
    path("importar/", views.importar, name="importar"),
    path("importar/plantilla/", views.plantilla, name="plantilla"),
    path("egresados/", views.egresados, name="egresados"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/ficha.pdf", views.ficha_pdf, name="ficha_pdf"),
    path("<int:pk>/inactivar/", views.marcar_inactivo, name="inactivar"),
    path("<int:pk>/reactivar/", views.reactivar, name="reactivar"),
    path("<int:pk>/apoderados/vincular/", views.vincular_apoderado, name="vincular_apoderado"),
    path("vinculos/<int:pk>/quitar/", views.desvincular_apoderado, name="desvincular_apoderado"),
    path("apoderados/<int:pk>/editar/", views.editar_apoderado, name="editar_apoderado"),
    path("cursos/", views.cursos, name="cursos"),
    path("cursos/nuevo/", views.curso_form, name="curso_crear"),
    path("cursos/nominas.pdf", views.cursos_pdf, name="cursos_pdf"),
    path("cursos/<int:pk>/", views.curso_detalle, name="curso"),
    path("cursos/<int:pk>/editar/", views.curso_form, name="curso_editar"),
    path("cursos/<int:pk>/nomina.pdf", views.cursos_pdf, name="curso_pdf"),
    path("promocion/", views.promocion, name="promocion"),
    path("promocion/revisar/", views.promocion_revisar, name="promocion_revisar"),
    path("promocion/procesar/", views.promocion_procesar, name="promocion_procesar"),
]
