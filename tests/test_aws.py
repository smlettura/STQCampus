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

    def test_tarea_diaria_recupera_dias_sin_copia(self):
        import datetime
        from unittest import mock
        from django.utils import timezone
        from apps.auditoria.servicios import registrar
        from apps.core import tareas

        registrar(None, "consulta", "prueba", None)
        hoy = timezone.localdate()
        dentro_de_4 = hoy + datetime.timedelta(days=4)        # el servidor estuvo apagado 4 días
        esperados = [hoy + datetime.timedelta(days=d) for d in range(4)]
        self.assertEqual(tareas.dias_por_exportar(dentro_de_4), esperados)
        with mock.patch.object(tareas.timezone, "localdate", return_value=dentro_de_4):
            primero = tareas.tarea_diaria()
            segundo = tareas.tarea_diaria()                   # una segunda ejecución no vuelve a escribir
        for fecha in esperados:
            self.assertTrue((settings.BITACORA_EXPORT_DIR / ("bitacora_%s.jsonl" % fecha.isoformat())).exists())
        self.assertGreater(primero["bitacora_exportada"], 0)
        self.assertEqual(segundo["bitacora_exportada"], 0)

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
