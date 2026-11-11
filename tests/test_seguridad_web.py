"""Revisión de seguridad web (OWASP Top 10): XSS, inyección, CSRF, redirección abierta, sesión y adjuntos."""
import datetime

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.casos.models import Caso, SesionSeguimiento
from apps.evaluacion.models import Informe

from .base import CLAVE, PruebaBase

ATAQUE = '<script>alert("x")</script><img src=x onerror=alert(1)>'


class XssTest(PruebaBase):
    """Todo texto ingresado por usuarios se escapa al mostrarse (A03: inyección)."""

    def setUp(self):
        self.estudiante.nombre_social = ATAQUE[:40]
        self.estudiante.save()
        self.caso = Caso.objects.create(estudiante=self.estudiante, tipo_proceso="seguimiento", responsable=self.psicologa,
                                        fecha_apertura=timezone.localdate() - datetime.timedelta(days=2))
        SesionSeguimiento.objects.create(caso=self.caso, profesional=self.psicologa, motivo="conducta",
                                         fecha_hora=timezone.now() - datetime.timedelta(hours=3), nota=ATAQUE)
        self.informe = Informe.objects.create(caso=self.caso, tipo="seguimiento", contenido="### Título\n* " + ATAQUE)

    def _sin_html_activo(self, url):
        r = self.cliente(self.psicologa).get(url)
        self.assertEqual(r.status_code, 200, url)
        html = r.content.decode()
        self.assertNotIn("<script>alert", html, url)
        self.assertNotIn("<img src=x", html, url)

    def test_paginas_escapan_el_contenido(self):
        for url in (reverse("estudiantes:detalle", args=[self.estudiante.pk]), reverse("casos:detalle", args=[self.caso.pk]),
                    reverse("evaluacion:informe", args=[self.informe.pk]), reverse("estudiantes:lista")):
            self._sin_html_activo(url)

    def test_sugerencias_devuelven_json_y_no_html(self):
        r = self.cliente(self.psicologa).get(reverse("estudiantes:sugerencias"), {"q": self.estudiante.primer_nombre})
        self.assertEqual(r["Content-Type"], "application/json")


class InyeccionSqlTest(PruebaBase):
    """Las búsquedas usan el ORM con parámetros: textos con SQL no alteran la consulta."""

    def test_busquedas_con_sql(self):
        cli = self.cliente(self.psicologa)
        for q in ("' OR '1'='1", "1; DROP TABLE estudiante; --", "%", "\\", "' UNION SELECT correo FROM usuario --"):
            for nombre in ("estudiantes:lista", "casos:lista", "casos:registrar_atencion"):
                self.assertEqual(cli.get(reverse(nombre), {"q": q}).status_code, 200, (nombre, q))
            datos = cli.get(reverse("estudiantes:sugerencias"), {"q": q}).json()
            self.assertEqual(datos["resultados"], [], q)


class CsrfTest(PruebaBase):
    """Los formularios rechazan envíos sin token CSRF (A01/A08)."""

    def test_post_sin_token_rechazado(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.psicologa)
        s = c.session
        s["mfa_ok"] = True
        s.save()
        r = c.post(reverse("convivencia:anotacion_nueva"), {"estudiante": self.estudiante.pk, "tipo": "positiva",
                                                             "descripcion": "Intento sin token", "fecha": "2026-11-01"})
        self.assertEqual(r.status_code, 403)


class SesionYRedireccionTest(PruebaBase):
    """Ingreso sin redirección abierta (A01) y cierre de sesión efectivo (A07)."""

    def test_no_redirige_a_otro_sitio_tras_ingresar(self):
        r = self.client.post(reverse("cuentas:login") + "?next=https://sitio-malicioso.example/robo",
                             {"username": self.profesor.correo, "password": CLAVE}, HTTP_HOST="localhost")
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("sitio-malicioso", r["Location"])

    def test_cerrar_sesion_invalida_la_sesion(self):
        c = self.cliente(self.psicologa)
        self.assertEqual(c.get(reverse("estudiantes:lista")).status_code, 200)
        c.post(reverse("cuentas:salir"))
        r = c.get(reverse("estudiantes:lista"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("cuentas:login"), r["Location"])

    def test_metodo_no_permitido(self):
        self.assertEqual(self.cliente(self.psicologa).get(reverse("ia:solicitar")).status_code, 405)


class AdjuntosTest(PruebaBase):
    """Los adjuntos se validan por su contenido real, no por la extensión (A04/A08)."""

    def setUp(self):
        self.caso = Caso.objects.create(estudiante=self.estudiante, tipo_proceso="seguimiento", responsable=self.psicologa)

    def test_html_disfrazado_de_pdf_rechazado(self):
        falso = SimpleUploadedFile("informe.pdf", b"<html><script>alert(1)</script></html>", content_type="application/pdf")
        r = self.cliente(self.psicologa).post(reverse("casos:documento", args=[self.caso.pk]),
                                              {"tipo": "informe_externo", "archivo": falso})
        self.assertEqual(r.status_code, 200)                     # vuelve al formulario con error
        self.assertFalse(self.caso.documentos.exists())

    def test_ejecutable_rechazado(self):
        exe = SimpleUploadedFile("programa.exe", b"MZ\x90\x00" + b"\x00" * 100)
        self.cliente(self.psicologa).post(reverse("casos:documento", args=[self.caso.pk]), {"tipo": "informe_externo", "archivo": exe})
        self.assertFalse(self.caso.documentos.exists())

    def test_pdf_real_aceptado(self):                        # control: la validación no rechaza todo
        pdf = SimpleUploadedFile("informe.pdf", b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n", content_type="application/pdf")
        r = self.cliente(self.psicologa).post(reverse("casos:documento", args=[self.caso.pk]),
                                              {"tipo": "informe_externo", "archivo": pdf})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.caso.documentos.count(), 1)


class EnumeracionTest(PruebaBase):
    """El ingreso no revela si un correo existe (A07)."""

    def test_mismo_mensaje_para_correo_inexistente_y_clave_incorrecta(self):
        from django.core.cache import cache
        cache.clear()
        a = self.client.post(reverse("cuentas:login"), {"username": self.profesor.correo, "password": "Incorrecta2026"})
        cache.clear()
        b = self.client.post(reverse("cuentas:login"), {"username": "nadie@demo.cl", "password": "Incorrecta2026"})
        self.assertEqual(a.status_code, b.status_code)
        errores = lambda r: [str(e) for e in r.context["form"].non_field_errors()]
        self.assertEqual(errores(a), errores(b))
