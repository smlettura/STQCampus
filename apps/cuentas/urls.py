from django.urls import path

from . import views

app_name = "cuentas"

urlpatterns = [
    path("login/", views.IngresoView.as_view(), name="login"),
    path("salir/", views.SalirView.as_view(), name="salir"),
    path("2fa/configurar/", views.configurar_2fa, name="configurar_2fa"),
    path("2fa/verificar/", views.verificar_2fa, name="verificar_2fa"),
    path("mi-cuenta/", views.mi_cuenta, name="mi_cuenta"),
    path("mi-cuenta/editar/", views.perfil_editar, name="perfil_editar"),
    path("cambiar-contrasena/", views.cambiar_contrasena, name="cambiar_contrasena"),
    path("restablecer/", views.RestablecerView.as_view(), name="restablecer"),
    path("restablecer/enviado/", views.RestablecerEnviadoView.as_view(), name="restablecer_enviado"),
    path("restablecer/<uidb64>/<token>/", views.RestablecerConfirmarView.as_view(), name="restablecer_confirmar"),
    path("restablecer/listo/", views.RestablecerListoView.as_view(), name="restablecer_listo"),
    path("usuarios/", views.usuarios, name="usuarios"),
    path("usuarios/sugerencias/", views.usuarios_sugerencias, name="usuarios_sugerencias"),
    path("usuarios/nuevo/", views.usuario_crear, name="usuario_crear"),
    path("usuarios/<int:pk>/", views.usuario, name="usuario"),
    path("usuarios/<int:pk>/restablecer-2fa/", views.restablecer_2fa, name="restablecer_2fa"),
    path("asignaciones/<int:pk>/finalizar/", views.asignacion_finalizar, name="asignacion_finalizar"),
]
