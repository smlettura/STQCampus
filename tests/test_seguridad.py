"""Cifrado de campos (RNF-01), bitácora inmutable (RNF-03), control de acceso (RNF-02) y segundo factor."""
import datetime

import pyotp
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.test import override_settings
from django.urls import reverse

from apps.auditoria.models import BitacoraInmutableError, EventoAuditoria
from apps.auditoria.servicios import registrar, verificar_cadena
from apps.casos.models import Caso, SesionSeguimiento
from apps.core.cifrado import ErrorDeCifrado, cifrar_texto, descifrar_texto

from .base import CLAVE, PruebaBase


class CifradoTest(PruebaBase):
    def test_ida_y_vuelta_y_contexto(self):
        token = cifrar_texto("diagnóstico reservado", "tabla.columna")
        self.assertEqual(descifrar_texto(token, "tabla.columna"), "diagnóstico reservado")
        with self.assertRaises(ErrorDeCifrado):       # copiado a otra columna: no se descifra
            descifrar_texto(token, "otra_tabla.columna")

    def test_alteracion_detectada(self):
        token = bytearray(cifrar_texto("nota", "t.c"))
        token[-1] ^= 1
        with self.assertRaises(ErrorDeCifrado):
            descifrar_texto(bytes(token), "t.c")

    def test_rotacion_de_claves(self):
        token = cifrar_texto("texto antiguo", "t.c")
        claves = {"k2": b"\x02" * 32, **settings.CIFRADO_CLAVES}
        with override_settings(CIFRADO_CLAVES=claves, CIFRADO_CLAVE_ACTIVA="k2"):
            self.assertEqual(descifrar_texto(token, "t.c"), "texto antiguo")
            nuevo = cifrar_texto("texto nuevo", "t.c")
            self.assertIn(b"k2", nuevo[:6])

    def test_la_base_guarda_solo_texto_cifrado(self):
        caso = Caso.objects.create(estudiante=self.estudiante, tipo_proceso="seguimiento", responsable=self.psicologa)
        s = SesionSeguimiento.objects.create(caso=caso, profesional=self.psicologa, fecha_hora=caso_fecha(),
                                             nota="Relato confidencial de la sesión")
        with connection.cursor() as c:
            c.execute("SELECT nota FROM sesion_seguimiento WHERE id_sesion = %s", [s.pk])
            crudo = bytes(c.fetchone()[0])
        self.assertNotIn(b"confidencial", crudo)
        self.assertEqual(SesionSeguimiento.objects.get(pk=s.pk).nota, "Relato confidencial de la sesión")


def caso_fecha():
    from django.utils import timezone
    return timezone.now() - datetime.timedelta(minutes=5)


class BitacoraTest(PruebaBase):
    def test_cadena_integra_y_alteracion_detectada(self):
        for i in range(3):
            registrar(self.psicologa, "consulta", "caso", i)
        self.assertTrue(verificar_cadena()[0])
        evento = EventoAuditoria.objects.order_by("id")[1]
        with connection.cursor() as c:     # alguien con acceso directo a la base altera un evento
            c.execute("UPDATE evento_auditoria SET detalle = 'manipulado' WHERE id_evento = %s", [evento.pk])
        integra, id_roto, _ = verificar_cadena()
        self.assertFalse(integra)
        self.assertEqual(id_roto, evento.pk)

    def test_la_aplicacion_no_modifica_ni_borra(self):
        e = registrar(None, "consulta", "prueba", None)
        e.detalle = "cambio"
        with self.assertRaises(BitacoraInmutableError):
            e.save()
        with self.assertRaises(BitacoraInmutableError):
            e.delete()
        with self.assertRaises(BitacoraInmutableError):
            EventoAuditoria.objects.all().update(detalle="x")
        with self.assertRaises(BitacoraInmutableError):
            EventoAuditoria.objects.all().delete()


class AccesoTest(PruebaBase):
    def setUp(self):
        self.caso = Caso.objects.create(estudiante=self.estudiante, tipo_proceso="seguimiento", responsable=self.psicologa)
        SesionSeguimiento.objects.create(caso=self.caso, profesional=self.psicologa, fecha_hora=caso_fecha(),
                                         nota="Nota del equipo psicosocial")

    def test_profesor_jefe_solo_ve_su_curso(self):
        c = self.cliente(self.profesor)
        self.assertEqual(c.get(reverse("estudiantes:detalle", args=[self.estudiante.pk])).status_code, 200)
        self.assertEqual(c.get(reverse("estudiantes:detalle", args=[self.estudiante2.pk])).status_code, 403)
        self.assertEqual(c.get(reverse("casos:detalle", args=[self.caso.pk])).status_code, 403)

    def test_coordinacion_pie_no_ve_casos_de_seguimiento_ni_notas(self):
        c = self.cliente(self.pie)
        self.assertEqual(c.get(reverse("casos:detalle", args=[self.caso.pk])).status_code, 403)
        caso_pie = Caso.objects.create(estudiante=self.estudiante, tipo_proceso="pie_nee", responsable=self.pie)
        SesionSeguimiento.objects.create(caso=caso_pie, profesional=self.psicologa, fecha_hora=caso_fecha(),
                                         nota="Contenido clínico reservado")
        r = c.get(reverse("casos:detalle", args=[caso_pie.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Contenido clínico reservado")

    def test_administrador_sin_acceso_clinico(self):
        c = self.cliente(self.admin)
        self.assertEqual(c.get(reverse("casos:detalle", args=[self.caso.pk])).status_code, 403)
        self.assertEqual(c.get(reverse("cuentas:usuarios")).status_code, 200)

    def test_nota_privada_solo_para_su_autora(self):
        SesionSeguimiento.objects.create(caso=self.caso, profesional=self.psicologa, fecha_hora=caso_fecha(),
                                         nota="Anotación privada de la autora", nivel_acceso="autora")
        self.assertContains(self.cliente(self.psicologa).get(reverse("casos:detalle", args=[self.caso.pk])),
                            "Anotación privada de la autora")
        self.assertNotContains(self.cliente(self.psicologa2).get(reverse("casos:detalle", args=[self.caso.pk])),
                               "Anotación privada de la autora")

    def test_acceso_denegado_queda_en_bitacora(self):
        self.cliente(self.profesor).get(reverse("casos:detalle", args=[self.caso.pk]))
        self.assertTrue(EventoAuditoria.objects.filter(usuario=self.profesor, accion="acceso_denegado").exists())

    def test_consulta_de_caso_queda_en_bitacora(self):
        self.cliente(self.psicologa).get(reverse("casos:detalle", args=[self.caso.pk]))
        self.assertTrue(EventoAuditoria.objects.filter(usuario=self.psicologa, accion="consulta", entidad="caso",
                                                       id_entidad=self.caso.pk).exists())

    def test_cabeceras_de_seguridad(self):
        r = self.cliente(self.psicologa).get(reverse("core:inicio"))
        self.assertIn("script-src 'self'", r["Content-Security-Policy"])
        self.assertEqual(r["Cache-Control"], "no-store")
        self.assertEqual(r["X-Frame-Options"], "DENY")


class SegundoFactorTest(PruebaBase):
    def setUp(self):
        cache.clear()

    def test_perfil_clinico_debe_configurar_2fa(self):
        c = self.cliente(self.psicologa, mfa=False)
        r = c.get(reverse("casos:lista"))
        self.assertRedirects(r, reverse("cuentas:configurar_2fa") + "?next=%2Fcasos%2F", fetch_redirect_response=False)
        r = c.get(reverse("api:resumen"))
        self.assertEqual(r.status_code, 403)

    def test_profesor_jefe_no_requiere_2fa(self):
        self.assertEqual(self.cliente(self.profesor, mfa=False).get(reverse("estudiantes:lista")).status_code, 200)

    def test_configuracion_y_verificacion_sin_reutilizar_codigo(self):
        c = self.cliente(self.psicologa, mfa=False)
        c.get(reverse("cuentas:configurar_2fa"))
        secreto = c.session["totp_pendiente"]
        codigo = pyotp.TOTP(secreto).now()
        r = c.post(reverse("cuentas:configurar_2fa"), {"codigo": codigo})
        self.assertEqual(r.status_code, 302)
        self.psicologa.refresh_from_db()
        self.assertTrue(self.psicologa.mfa_activo)
        # Nueva sesión: el mismo código no puede reutilizarse.
        c2 = self.cliente(self.psicologa, mfa=False)
        r = c2.post(reverse("cuentas:verificar_2fa"), {"codigo": codigo})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Código incorrecto")

    def test_bloqueo_tras_intentos_fallidos(self):
        c = self.client
        for _ in range(settings.LOGIN_MAX_INTENTOS):
            c.post(reverse("cuentas:login"), {"username": "psi@demo.cl", "password": "incorrecta"})
        r = c.post(reverse("cuentas:login"), {"username": "psi@demo.cl", "password": CLAVE})
        self.assertContains(r, "Demasiados intentos fallidos")
        self.assertTrue(EventoAuditoria.objects.filter(accion="acceso_denegado", entidad="sesion").exists())

    def test_contrasena_debil_rechazada(self):
        c = self.cliente(self.admin)
        r = c.post(reverse("cuentas:usuario_crear"), {"nombre_completo": "Nuevo Usuario", "correo": "nuevo@demo.cl",
                                                      "password1": "12345678", "password2": "12345678"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(self.admin.__class__.objects.filter(correo="nuevo@demo.cl").exists())

    def test_no_quedar_sin_administradores(self):
        c = self.cliente(self.admin)
        asignacion = self.admin.asignaciones.get(rol__codigo="administrador")
        c.post(reverse("cuentas:asignacion_finalizar", args=[asignacion.pk]))
        asignacion.refresh_from_db()
        self.assertIsNone(asignacion.vigente_hasta)


class DesfaseRelojTest(PruebaBase):
    """Si el reloj del teléfono o del computador está desajustado, se explica la causa (sin aceptar el código)."""

    def test_detecta_desfase_de_minutos_y_de_horas(self):
        from apps.cuentas import totp
        secreto = pyotp.random_base32()
        ahora = 1_790_000_000
        self.assertEqual(totp.desfase_probable(secreto, pyotp.TOTP(secreto).at(ahora + 150), ahora), 150)
        self.assertEqual(totp.desfase_probable(secreto, pyotp.TOTP(secreto).at(ahora - 3 * 3600), ahora), -3 * 3600)
        self.assertIn("3 horas", totp.mensaje_desfase(-3 * 3600))
        self.assertIsNone(totp.desfase_probable(secreto, "12345", ahora))

    def test_configurar_explica_el_desfase_y_no_acepta_el_codigo(self):
        import time
        c = self.cliente(self.psicologa, mfa=False)
        c.get(reverse("cuentas:configurar_2fa"))
        secreto = c.session["totp_pendiente"]
        r = c.post(reverse("cuentas:configurar_2fa"), {"codigo": pyotp.TOTP(secreto).at(time.time() + 3 * 3600)})
        self.assertContains(r, "corresponde a otra hora")
        self.psicologa.refresh_from_db()
        self.assertFalse(self.psicologa.mfa_activo)

    def test_comando_restablece_el_segundo_factor(self):
        import io

        from django.core.management import call_command
        self.psicologa.secreto_totp, self.psicologa.mfa_activo = "JBSWY3DPEHPK3PXP", True
        self.psicologa.save()
        call_command("restablecer_2fa", self.psicologa.correo, stdout=io.StringIO())
        self.psicologa.refresh_from_db()
        self.assertEqual((self.psicologa.mfa_activo, self.psicologa.secreto_totp), (False, None))
