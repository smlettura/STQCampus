"""Interfaz «panel analítico»: menú por rol, enlace activo, recursos locales (compatibles con la CSP) y segundo factor."""
from pathlib import Path

from django.conf import settings
from django.test import Client
from django.urls import reverse

from apps.core.menu import construir_menu

from .base import PruebaBase


class MenuTest(PruebaBase):
    def test_menu_segun_permisos_del_rol(self):
        profesor = construir_menu("/", self.profesor.codigos_permiso())
        self.assertEqual([g["clave"] for g in profesor], ["atencion", "estudiantes", "convivencia", "alertas"])
        atencion = next(g for g in profesor if g["clave"] == "atencion")
        self.assertEqual([e["nombre"] for e in atencion["enlaces"]], ["Derivar al equipo"])
        convivencia = next(g for g in profesor if g["clave"] == "convivencia")
        self.assertEqual([e["nombre"] for e in convivencia["enlaces"]], ["Anotaciones"])
        admin = construir_menu("/", self.admin.codigos_permiso())
        self.assertNotIn("atencion", [g["clave"] for g in admin])          # el administrador no ve casos clínicos
        # Orden del prototipo v1 para el equipo psicosocial
        psicologa = [g["nombre"] for g in construir_menu("/", self.psicologa.codigos_permiso())]
        self.assertEqual(psicologa[:6], ["Atención psicosocial", "Estudiantes", "Convivencia", "Protocolos",
                                         "Plan de gestión", "Indicadores"])

    def test_gana_el_prefijo_mas_largo(self):
        menu = construir_menu("/casos/derivaciones/", self.psicologa.codigos_permiso())
        activos = [e["nombre"] for g in menu for e in g["enlaces"] if e["activo"]]
        self.assertEqual(activos, ["Derivaciones"])
        menu = construir_menu("/casos/12/", self.psicologa.codigos_permiso())
        self.assertEqual([e["nombre"] for g in menu for e in g["enlaces"] if e["activo"]], ["Fichas de estudiantes"])
        menu = construir_menu("/casos/resumen/", self.psicologa.codigos_permiso())
        self.assertEqual([e["nombre"] for g in menu for e in g["enlaces"] if e["activo"]], ["Resumen"])

    def test_pagina_muestra_menu_y_buscador(self):
        r = self.cliente(self.psicologa).get(reverse("core:inicio"), follow=True)
        self.assertRedirects(r, reverse("casos:resumen"))
        self.assertContains(r, 'class="lateral"')
        self.assertContains(r, "Ctrl K")
        self.assertContains(r, 'name="q"')
        self.assertContains(r, "Registrar alerta")

    def test_sin_segundo_factor_no_hay_menu(self):
        r = self.cliente(self.psicologa, mfa=False).get(reverse("cuentas:configurar_2fa"))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'class="lateral"')
        self.assertNotContains(r, 'name="q"')


class RecursosTest(PruebaBase):
    def test_ingreso_con_escudo_y_marca(self):
        r = Client().get(reverse("cuentas:login"))
        self.assertContains(r, "img/escudo.png")
        self.assertContains(r, settings.NOMBRE_MARCA)

    def test_estilos_sin_recursos_externos(self):
        css = (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text(encoding="utf-8")
        self.assertNotIn("http://", css)
        self.assertNotIn("https://", css)
        fuentes = Path(settings.BASE_DIR) / "static" / "fonts"
        for nombre in ("manrope-latin-400-normal.woff2", "jetbrains-mono-latin-500-normal.woff2"):
            self.assertTrue((fuentes / nombre).exists(), nombre)
