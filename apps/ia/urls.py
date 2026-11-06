from django.urls import path

from . import agente_api, views

app_name = "ia"

urlpatterns = [
    path("generar-informe/", views.generar_informe, name="generar_informe"),
    path("solicitar/", views.solicitar, name="solicitar"),
    path("solicitudes/<int:pk>/", views.solicitud, name="solicitud"),
    path("borradores/<int:pk>/validar/", views.validar, name="validar"),
    path("borradores/<int:pk>/descartar/", views.descartar, name="descartar"),
    path("borradores/<int:pk>/observacion/", views.retroalimentar, name="retroalimentar"),
    # Agente del equipo propio (token; sin sesión)
    path("agente/latido/", agente_api.latido, name="agente_latido"),
    path("agente/tomar/", agente_api.tomar, name="agente_tomar"),
    path("agente/<int:pk>/resultado/", agente_api.resultado, name="agente_resultado"),
]
