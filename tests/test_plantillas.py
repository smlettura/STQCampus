"""Todas las plantillas compilan (detecta errores de sintaxis en vistas que ninguna otra prueba abre)."""
import pathlib

from django.conf import settings
from django.template.loader import get_template
from django.test import SimpleTestCase


class PlantillasCompilanTest(SimpleTestCase):
    def test_todas_las_plantillas_compilan(self):
        raiz = pathlib.Path(settings.BASE_DIR) / "templates"
        archivos = sorted(raiz.rglob("*.html"))
        self.assertGreater(len(archivos), 20)
        for f in archivos:
            with self.subTest(plantilla=str(f.relative_to(raiz))):
                get_template(str(f.relative_to(raiz)))
