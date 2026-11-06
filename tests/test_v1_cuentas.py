"""Acceso del prototipo v1: «Recordarme», «¿Olvidaste tu contraseña?», primer ingreso y «Mi perfil»."""
import re

from django.core import mail
from django.test import Client
from django.urls import reverse

from apps.cuentas.models import Usuario

from .base import CLAVE, PruebaBase


class IngresoTest(PruebaBase):
    def test_recordarme_guarda_solo_el_correo(self):
        c = Client()
        r = c.post(reverse("cuentas:login"), {"username": "profe@demo.cl", "password": CLAVE, "recordar": "on"})
        self.assertEqual(r.status_code, 302)
        galleta = r.cookies["correo_recordado"]
        self.assertTrue(galleta["httponly"])
        self.assertNotIn(CLAVE, galleta.value)
        c.post(reverse("cuentas:salir"))
        self.assertContains(c.get(reverse("cuentas:login")), 'value="profe@demo.cl"')
        r = c.post(reverse("cuentas:login"), {"username": "profe@demo.cl", "password": CLAVE})
        self.assertEqual(r.cookies["correo_recordado"].value, "")          # sin «Recordarme» se borra

    def test_restablecer_contrasena_por_correo(self):
        c = Client()
        r = c.post(reverse("cuentas:restablecer"), {"email": "no-existe@demo.cl"})
        self.assertRedirects(r, reverse("cuentas:restablecer_enviado"))       # no revela si la cuenta existe
        self.assertEqual(len(mail.outbox), 0)
        c.post(reverse("cuentas:restablecer"), {"email": "PROFE@demo.cl"})
        self.assertEqual(len(mail.outbox), 1)
        enlace = re.search(r"http://testserver(/cuentas/restablecer/\S+/)", mail.outbox[0].body).group(1)
        r = c.get(enlace, follow=True)
        nueva = "OtraClave#2026x"
        r = c.post(r.redirect_chain[-1][0], {"new_password1": nueva, "new_password2": nueva})
        self.assertRedirects(r, reverse("cuentas:restablecer_listo"))
        self.assertTrue(Usuario.objects.get(correo="profe@demo.cl").check_password(nueva))


class PrimerIngresoPerfilTest(PruebaBase):
    def test_primer_ingreso_obliga_a_cambiar_la_contrasena(self):
        c = self.cliente(self.admin)
        c.post(reverse("cuentas:usuario_crear"), {"nombre_completo": "Nueva Docente", "correo": "nueva@demo.cl",
                                                   "password1": "Inicial#2026x", "password2": "Inicial#2026x"})
        nueva = Usuario.objects.get(correo="nueva@demo.cl")
        self.assertTrue(nueva.cambio_contrasena_pendiente)
        c2 = self.cliente(nueva)
        self.assertRedirects(c2.get(reverse("core:inicio")), reverse("cuentas:cambiar_contrasena"))
        c2.post(reverse("cuentas:cambiar_contrasena"), {"old_password": "Inicial#2026x", "new_password1": "Personal#2026y",
                                                         "new_password2": "Personal#2026y"})
        nueva.refresh_from_db()
        self.assertFalse(nueva.cambio_contrasena_pendiente)
        self.assertIsNotNone(nueva.contrasena_actualizada)
        self.assertEqual(c2.get(reverse("core:inicio")).status_code, 200)

    def test_perfil_actualiza_telefono_normalizado(self):
        c = self.cliente(self.psicologa)
        self.assertContains(c.get(reverse("cuentas:mi_cuenta")), "Información de la cuenta")
        self.assertContains(c.post(reverse("cuentas:perfil_editar"), {"telefono": "123", "especialidad": ""}), "teléfono")
        c.post(reverse("cuentas:perfil_editar"), {"telefono": "9 1234 5678", "especialidad": " Psicóloga  educacional "})
        self.psicologa.refresh_from_db()
        self.assertEqual((self.psicologa.telefono, self.psicologa.especialidad), ("+56912345678", "Psicóloga educacional"))
