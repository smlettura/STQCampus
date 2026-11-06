"""La antirrepetición del segundo factor y el bloqueo por intentos usan una caché compartida entre procesos."""
import pyotp
from django.conf import settings
from django.core.cache.backends.db import DatabaseCache
from django.db import connection
from django.test import TestCase, override_settings

from apps.cuentas import totp

CACHE_BD = {"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "cache_compartida"}}


class CacheCompartidaTest(TestCase):
    def test_configuracion_usa_la_base_de_datos(self):
        self.assertEqual(settings.CACHES["default"]["BACKEND"], "django.core.cache.backends.db.DatabaseCache")
        self.assertIn("cache_compartida", connection.introspection.table_names())

    @override_settings(CACHES=CACHE_BD)
    def test_codigo_totp_no_se_reutiliza_en_otro_trabajador(self):
        secreto = pyotp.random_base32()
        codigo = pyotp.TOTP(secreto).now()
        self.assertTrue(totp.verificar_codigo(secreto, codigo, 4242))
        self.assertFalse(totp.verificar_codigo(secreto, codigo, 4242))
        # Otro trabajador de Gunicorn abre su propia instancia de la caché: ve el mismo registro en la base de datos.
        otro_trabajador = DatabaseCache("cache_compartida", {})
        self.assertTrue(otro_trabajador.get("totp_usado:%s:%s" % (4242, codigo)))
        self.assertFalse(otro_trabajador.add("totp_usado:%s:%s" % (4242, codigo), True, 120))
