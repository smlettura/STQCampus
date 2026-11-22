"""La región de AWS es una sola (AWS_REGION, por defecto us-east-1) y la usan Secrets Manager y S3."""
import importlib.util
import json
import os
import sys
import types
from pathlib import Path
from unittest import TestCase, mock

RUTA_SETTINGS = Path(__file__).resolve().parent.parent / "config" / "settings.py"


def cargar_settings(entorno):
    """Carga config/settings.py como un módulo aparte, con un entorno controlado y boto3 simulado."""
    regiones = []

    class ClienteFalso:
        def get_secret_value(self, SecretId):
            return {"SecretString": json.dumps({})}

    def client(servicio, region_name=None):
        regiones.append((servicio, region_name))
        return ClienteFalso()

    boto3_falso = types.ModuleType("boto3"); boto3_falso.client = client
    base = {"DJANGO_SECRET_KEY": "x" * 50, "DJANGO_DEBUG": "1", "AWS_SECRETS_ID": "stq/pruebas",
            "ALMACENAMIENTO": "s3", "AWS_S3_ADJUNTOS": "adj", "AWS_S3_BITACORA": "bit", "AWS_REGION": ""}
    base.update(entorno)
    with mock.patch.dict(os.environ, base), mock.patch.dict(sys.modules, {"boto3": boto3_falso}):
        spec = importlib.util.spec_from_file_location("settings_region_prueba", RUTA_SETTINGS)
        modulo = importlib.util.module_from_spec(spec); spec.loader.exec_module(modulo)
    return modulo, regiones


class PruebasRegionAWS(TestCase):
    def test_region_por_defecto_us_east_1(self):
        s, regiones = cargar_settings({})
        self.assertEqual(regiones, [("secretsmanager", "us-east-1")])
        self.assertEqual(s.STORAGES["adjuntos"]["OPTIONS"]["region_name"], "us-east-1")
        self.assertEqual(s.STORAGES["bitacora"]["OPTIONS"]["region_name"], "us-east-1")

    def test_ambos_clientes_siguen_aws_region(self):
        s, regiones = cargar_settings({"AWS_REGION": "eu-west-1"})
        self.assertEqual(regiones, [("secretsmanager", "eu-west-1")])
        self.assertEqual(s.STORAGES["adjuntos"]["OPTIONS"]["region_name"], "eu-west-1")
        self.assertEqual(s.AWS_REGION, "eu-west-1")
