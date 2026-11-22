from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LoginView, LogoutView
from django.core.cache import cache
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

from apps.auditoria.servicios import registrar

from . import totp
from .forms import (AsignacionRolForm, CambioContrasenaForm, CodigoForm, IngresoForm, NuevaContrasenaForm, PerfilForm,
                    RestablecerContrasenaForm, UsuarioCrearForm, UsuarioEditarForm, otros_administradores)
from .models import Usuario, UsuarioRol
from .permisos import permiso_requerido

MAX_INTENTOS_2FA = 5


def _siguiente(request, defecto="core:inicio"):
    destino = request.POST.get("next") or request.GET.get("next")
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()},
                                                   require_https=request.is_secure()):
        return destino
    return defecto


COOKIE_CORREO = "correo_recordado"


class IngresoView(LoginView):
    template_name = "cuentas/ingreso.html"
    authentication_form = IngresoForm
    redirect_authenticated_user = True

    def get_initial(self):
        inicial = super().get_initial()
        correo = self.request.get_signed_cookie(COOKIE_CORREO, default="", salt="ingreso")
        if correo:
            inicial.update({"username": correo, "recordar": True})
        return inicial

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        self.request.session["mfa_ok"] = False
        # «Recordarme» solo guarda el correo (firmado) para no tener que escribirlo; la sesión igual expira a los 30 min.
        if form.cleaned_data.get("recordar"):
            respuesta.set_signed_cookie(COOKIE_CORREO, form.get_user().correo, salt="ingreso",
                                        max_age=settings.RECORDAR_CORREO_DIAS * 86400, httponly=True, samesite="Lax",
                                        secure=self.request.is_secure())
        else:
            respuesta.delete_cookie(COOKIE_CORREO)
        return respuesta


class SalirView(LogoutView):
    next_page = "cuentas:login"


@login_required
def configurar_2fa(request):
    usuario = request.user
    if usuario.mfa_activo and usuario.secreto_totp and not request.session.get("mfa_ok"):
        return redirect("cuentas:verificar_2fa")          # reconfigurar exige haber pasado el segundo factor
    secreto = request.session.get("totp_pendiente")
    if not secreto:
        secreto = totp.nuevo_secreto()
        request.session["totp_pendiente"] = secreto
    form = CodigoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if totp.verificar_codigo(secreto, form.cleaned_data["codigo"], usuario.pk):
            usuario.secreto_totp = secreto
            usuario.mfa_activo = True
            usuario.save(update_fields=["secreto_totp", "mfa_activo"])
            request.session.pop("totp_pendiente", None)
            request.session["mfa_ok"] = True
            registrar(usuario, "modificacion", "usuario", usuario.pk, detalle="segundo factor configurado")
            messages.success(request, "Segundo factor activado. Desde ahora se le pedirá un código al ingresar.")
            return redirect(_siguiente(request))
        desfase = totp.desfase_probable(secreto, form.cleaned_data["codigo"])
        form.add_error("codigo", totp.mensaje_desfase(desfase) if desfase is not None else
                       "El código no es válido. Use la cuenta «STQCampus Bienestar» que acaba de escanear en esta "
                       "pantalla (si tiene otras con el mismo nombre, de intentos anteriores, elimínelas) y escriba el "
                       "código que se muestra ahora.")
    uri = totp.uri_aprovisionamiento(usuario.correo, secreto)
    return render(request, "cuentas/configurar_2fa.html", {
        "form": form, "qr": mark_safe(totp.qr_svg(uri)), "secreto": secreto, "next": _siguiente(request, ""),
        "ahora": timezone.localtime()})


@login_required
def verificar_2fa(request):
    usuario = request.user
    if not (usuario.mfa_activo and usuario.secreto_totp):
        return redirect("cuentas:configurar_2fa")
    clave = "intentos_2fa:%s" % usuario.pk
    form = CodigoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if totp.verificar_codigo(usuario.secreto_totp, form.cleaned_data["codigo"], usuario.pk):
            cache.delete(clave)
            request.session.cycle_key()
            request.session["mfa_ok"] = True
            registrar(usuario, "inicio_sesion", "sesion", usuario.pk, detalle="segundo factor correcto")
            return redirect(_siguiente(request))
        intentos = cache.get(clave, 0) + 1
        cache.set(clave, intentos, 15 * 60)
        registrar(usuario, "acceso_denegado", "sesion", usuario.pk, detalle="código de segundo factor inválido")
        if intentos >= MAX_INTENTOS_2FA:
            logout(request)
            messages.error(request, "Demasiados códigos incorrectos. Vuelva a iniciar sesión.")
            return redirect("cuentas:login")
        desfase = totp.desfase_probable(usuario.secreto_totp, form.cleaned_data["codigo"])
        form.add_error("codigo", (totp.mensaje_desfase(desfase) + " " if desfase is not None else "Código incorrecto. ")
                       + "Le quedan %d intentos." % (MAX_INTENTOS_2FA - intentos))
    return render(request, "cuentas/verificar_2fa.html", {"form": form, "next": _siguiente(request, ""),
                                                          "ahora": timezone.localtime()})


# ------------------------------------------------------------------ modo privado


@login_required
@require_POST
def privacidad_ocultar(request):
    """Un clic: oculta los datos sensibles en todas las pantallas de esta sesión."""
    from apps.core import privacidad
    request.session[privacidad.CLAVE_SESION] = True
    registrar(request.user, "modificacion", "sesion", request.user.pk, detalle="modo privado activado")
    messages.info(request, "Modo privado activado: los datos sensibles quedan ocultos.")
    return redirect(_siguiente(request))


@login_required
@require_POST
def privacidad_mostrar(request):
    """Un clic: vuelve a mostrar los datos sensibles en esta sesión."""
    from apps.core import privacidad
    request.session[privacidad.CLAVE_SESION] = False
    registrar(request.user, "modificacion", "sesion", request.user.pk, detalle="modo privado desactivado")
    messages.info(request, "Modo privado desactivado: los datos vuelven a verse.")
    return redirect(_siguiente(request))


@login_required
def mi_cuenta(request):
    """Mi perfil (prototipo v1): información de la cuenta y seguridad."""
    return render(request, "cuentas/mi_cuenta.html", {"u": request.user})


@login_required
def perfil_editar(request):
    form = PerfilForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        registrar(request.user, "modificacion", "usuario", request.user.pk, detalle="actualización de perfil")
        messages.success(request, "Información actualizada.")
        return redirect("cuentas:mi_cuenta")
    return render(request, "comun/formulario.html", {"form": form, "titulo": "Actualizar información",
                                                     "volver_url": reverse("cuentas:mi_cuenta")})


@login_required
def cambiar_contrasena(request):
    pendiente = request.user.cambio_contrasena_pendiente
    form = CambioContrasenaForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        update_session_auth_hash(request, form.user)
        registrar(request.user, "modificacion", "usuario", request.user.pk,
                  detalle="cambio de contraseña" + (" (primer ingreso)" if pendiente else ""))
        messages.success(request, "Contraseña actualizada.")
        return redirect("core:inicio" if pendiente else "cuentas:mi_cuenta")
    return render(request, "comun/formulario.html", {
        "form": form, "titulo": "Cambiar contraseña", "boton": "Actualizar contraseña",
        "volver_url": "" if pendiente else reverse("cuentas:mi_cuenta"),
        "advertencia": "Es su primer ingreso: reemplace la contraseña que le entregó el administrador por una personal."
        if pendiente else ""})


# ------------------------------------------------------------------ restablecer contraseña por correo
class RestablecerView(auth_views.PasswordResetView):
    template_name = "cuentas/restablecer.html"
    form_class = RestablecerContrasenaForm
    email_template_name = "cuentas/correo_restablecer.txt"
    subject_template_name = "cuentas/correo_restablecer_asunto.txt"
    success_url = reverse_lazy("cuentas:restablecer_enviado")

    def form_valid(self, form):
        registrar(None, "consulta", "sesion", None, detalle="solicitud de restablecimiento de contraseña")
        return super().form_valid(form)


class RestablecerEnviadoView(auth_views.PasswordResetDoneView):
    template_name = "cuentas/restablecer_enviado.html"


class RestablecerConfirmarView(auth_views.PasswordResetConfirmView):
    template_name = "cuentas/restablecer_confirmar.html"
    form_class = NuevaContrasenaForm
    success_url = reverse_lazy("cuentas:restablecer_listo")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        registrar(form.user, "modificacion", "usuario", form.user.pk, detalle="contraseña restablecida por correo")
        return respuesta


class RestablecerListoView(auth_views.PasswordResetCompleteView):
    template_name = "cuentas/restablecer_listo.html"


# ------------------------------------------------------------------ administración (RF-09)
@permiso_requerido("usuarios.administrar")
def usuarios(request):
    lista = Usuario.objects.prefetch_related("asignaciones__rol", "asignaciones__sede")
    q = request.GET.get("q", "").strip()
    if q:
        lista = lista.filter(nombre_completo__icontains=q) | lista.filter(correo__icontains=q)
    return render(request, "cuentas/usuarios.html", {"usuarios": lista, "q": q, "hoy": timezone.localdate()})


@permiso_requerido("usuarios.administrar")
def usuario_crear(request):
    form = UsuarioCrearForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario = form.save()
        registrar(request.user, "creacion", "usuario", usuario.pk)
        messages.success(request, "Usuario creado. Ahora asígnele al menos un rol.")
        return redirect("cuentas:usuario", usuario.pk)
    return render(request, "comun/formulario.html", {"form": form, "titulo": "Nuevo usuario",
                                                     "volver_url": reverse("cuentas:usuarios")})


@permiso_requerido("usuarios.administrar")
def usuario(request, pk):
    obj = get_object_or_404(Usuario, pk=pk)
    form_editar = UsuarioEditarForm(request.POST if request.POST.get("accion") == "editar" else None, instance=obj,
                                    editor=request.user)
    form_rol = AsignacionRolForm(request.POST if request.POST.get("accion") == "rol" else None, usuario=obj)
    if request.method == "POST":
        if request.POST.get("accion") == "editar" and form_editar.is_valid():
            form_editar.save()
            registrar(request.user, "modificacion", "usuario", obj.pk)
            messages.success(request, "Datos del usuario actualizados.")
            return redirect("cuentas:usuario", obj.pk)
        if request.POST.get("accion") == "rol" and form_rol.is_valid():
            asignacion = form_rol.save()
            registrar(request.user, "creacion", "usuario_rol", asignacion.pk, detalle="rol %s" % asignacion.rol.codigo)
            messages.success(request, "Rol asignado.")
            return redirect("cuentas:usuario", obj.pk)
    return render(request, "cuentas/usuario.html", {
        "obj": obj, "form_editar": form_editar, "form_rol": form_rol,
        "asignaciones": obj.asignaciones.select_related("rol", "sede").order_by("-vigente_desde"),
        "hoy": timezone.localdate()})


@require_POST
@permiso_requerido("usuarios.administrar")
def asignacion_finalizar(request, pk):
    asignacion = get_object_or_404(UsuarioRol, pk=pk)
    hoy = timezone.localdate()
    if asignacion.rol.codigo == "administrador" and not otros_administradores(asignacion.usuario).exists():
        messages.error(request, "No se puede quitar el rol: debe quedar al menos un administrador activo.")
    elif asignacion.vigente_hasta and asignacion.vigente_hasta < hoy:
        messages.info(request, "La asignación ya estaba finalizada.")
    else:
        asignacion.vigente_hasta = max(hoy, asignacion.vigente_desde)
        asignacion.save(update_fields=["vigente_hasta"])
        registrar(request.user, "modificacion", "usuario_rol", asignacion.pk, detalle="rol finalizado")
        messages.success(request, "Asignación finalizada.")
    return redirect("cuentas:usuario", asignacion.usuario_id)


@require_POST
@permiso_requerido("usuarios.administrar")
@transaction.atomic
def restablecer_2fa(request, pk):
    obj = get_object_or_404(Usuario, pk=pk)
    obj.secreto_totp = None
    obj.mfa_activo = False
    obj.save(update_fields=["secreto_totp", "mfa_activo"])
    registrar(request.user, "modificacion", "usuario", obj.pk, detalle="segundo factor restablecido")
    messages.success(request, "Segundo factor restablecido: el usuario deberá configurarlo en su próximo ingreso.")
    return redirect("cuentas:usuario", obj.pk)


@permiso_requerido("usuarios.administrar")
def usuarios_sugerencias(request):
    """Lista desplegable del buscador de usuarios (solo administración de cuentas)."""
    from django.http import JsonResponse
    from django.urls import reverse
    q = request.GET.get("q", "").strip()[:60]
    if len(q) < 2:
        return JsonResponse({"resultados": []})
    qs = (Usuario.objects.filter(nombre_completo__icontains=q) | Usuario.objects.filter(correo__icontains=q)).order_by("nombre_completo")
    return JsonResponse({"resultados": [
        {"id": u.pk, "texto": u.nombre_completo, "detalle": u.correo, "url": reverse("cuentas:usuario", args=[u.pk])}
        for u in qs[:8]]})
