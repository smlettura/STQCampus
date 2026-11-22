"""Formato de presentación de los informes (filtro formato_informe)."""
from django.test import SimpleTestCase

from apps.core.templatetags.ui import formato_informe


class FormatoInformeTest(SimpleTestCase):
    def test_titulos_vinetas_y_negrita(self):
        html = formato_informe("## Informe de atención\n\n### Antecedentes\n\nTexto uno.\nTexto dos.\n\n"
                               "* **16/08/2026:** Primera sesión.\n* Segunda.\n\n1. Uno\n2. Dos")
        self.assertNotIn("Informe de atención", html)          # el documento ya muestra el título
        self.assertIn("<h3>Antecedentes</h3>", html)
        self.assertIn("<p>Texto uno.<br>Texto dos.</p>", html)
        self.assertIn("<ul>\n<li><strong>16/08/2026:</strong> Primera sesión.</li>\n<li>Segunda.</li>\n</ul>", html)
        self.assertIn("<ol>\n<li>Uno</li>\n<li>Dos</li>\n</ol>", html)

    def test_escapa_html(self):
        html = formato_informe("* <script>alert(1)</script> **<b>x</b>**")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("<strong>&lt;b&gt;x&lt;/b&gt;</strong>", html)

    def test_marcas_para_revisar(self):
        html = formato_informe("[FUERA DE MI ALCANCE: nivel de riesgo]")
        self.assertIn('<span class="marca-revisar">[FUERA DE MI ALCANCE: nivel de riesgo]</span>', html)

    def test_texto_vacio(self):
        self.assertEqual(formato_informe(""), "")
        self.assertEqual(formato_informe(None), "")

    def test_omite_titulo_inicial_de_nivel_2_y_resalta_pendiente(self):
        html = formato_informe("## Derivación externa\n\n### Antecedentes\n\n[PENDIENTE: antecedentes]")
        self.assertNotIn("Derivación externa", html)
        self.assertIn('<span class="marca-revisar">[PENDIENTE: antecedentes]</span>', html)

    def test_titulo_sin_contenido_no_se_muestra(self):
        html = formato_informe("### Antecedentes\n\nTexto.\n\n### Advertencias para la profesional\n")
        self.assertIn("<h3>Antecedentes</h3>", html)
        self.assertNotIn("Advertencias", html)
