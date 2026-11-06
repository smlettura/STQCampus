"""Despliegue en AWS: tareas por comando de Django y almacenamiento de adjuntos (local o S3)."""
import io
import json

from django.conf import settings
from django.core.management import call_command

from apps.casos import almacenamiento

from .base import PruebaBase


class PruebasAWS(PruebaBase):
    def test_comando_tarea_diaria(self):
        salida = io.StringIO()
        call_command("ejecutar_tarea", "diaria", stdout=salida)
        resultado = json.loads(salida.getvalue())
        self.assertIn("avisos_reevaluacion", resultado)
        self.assertIn("bitacora_exportada", resultado)

    def test_comando_tarea_mensual(self):
        salida = io.StringIO()
        call_command("ejecutar_tarea", "mensual", stdout=salida)
        self.assertIn("retenciones_propuestas", json.loads(salida.getvalue()))

    def test_almacenamientos_definidos(self):
        self.assertIn("adjuntos", settings.STORAGES)
        self.assertIn("bitacora", settings.STORAGES)

    def test_clave_de_objeto_validada(self):
        with self.assertRaises(almacenamiento.AdjuntoAlteradoError):
            almacenamiento._clave("../config/settings.py")
        ruta, huella = almacenamiento.guardar_bytes(b"contenido de prueba")
        self.assertEqual(almacenamiento.leer_bytes(ruta, huella), b"contenido de prueba")
