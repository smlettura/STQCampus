"""Validaciones de datos de entrada: RUT, teléfono, archivos, fechas y textos."""
import datetime

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from apps.core.validadores import (calcular_dv, formatear_rut, normalizar_rut, normalizar_telefono, sumar_anios,
                                   validar_adjunto, validar_no_futuro, validar_texto_minimo)


class RutTest(SimpleTestCase):
    def test_digito_verificador(self):
        self.assertEqual(calcular_dv(11111111), "1")
        self.assertEqual(calcular_dv(12345678), "5")
        self.assertEqual(calcular_dv(5126663), "3")
        self.assertEqual(calcular_dv(10000013), "K")

    def test_formatos_aceptados_se_normalizan(self):
        for entrada in ["12.345.678-5", "12345678-5", "12345678-5 ", "123456785"]:
            self.assertEqual(normalizar_rut(entrada), "12345678-5")
        self.assertEqual(normalizar_rut("10.000.013-k"), "10000013-K")

    def test_rut_invalido(self):
        for entrada in ["12.345.678-9", "abc", "", "12-3", "123.45.678-5"]:
            with self.assertRaises(ValidationError, msg=entrada):
                normalizar_rut(entrada)

    def test_formatear(self):
        self.assertEqual(formatear_rut("12345678-5"), "12.345.678-5")


class TelefonoTest(SimpleTestCase):
    def test_normaliza(self):
        self.assertEqual(normalizar_telefono("9 1234 5678"), "+56912345678")
        self.assertEqual(normalizar_telefono("+56 9 1234 5678"), "+56912345678")
        self.assertEqual(normalizar_telefono("56912345678"), "+56912345678")
        self.assertEqual(normalizar_telefono(""), "")

    def test_rechaza_largo_incorrecto(self):
        for t in ["12345", "+56 9 1234 567", "teléfono"]:
            with self.assertRaises(ValidationError):
                normalizar_telefono(t)


class FechasTextoTest(SimpleTestCase):
    def test_no_futuro(self):
        validar_no_futuro(timezone.localdate())
        with self.assertRaises(ValidationError):
            validar_no_futuro(timezone.localdate() + datetime.timedelta(days=1))
        with self.assertRaises(ValidationError):
            validar_no_futuro(timezone.now() + datetime.timedelta(hours=1))

    def test_sumar_anios_29_febrero(self):
        self.assertEqual(sumar_anios(datetime.date(2024, 2, 29), 15), datetime.date(2039, 2, 28))

    def test_texto_minimo(self):
        v = validar_texto_minimo(10)
        v("suficiente texto")
        with self.assertRaises(ValidationError):
            v("   corto   ")


@override_settings(ADJUNTO_MAX_MB=1)
class AdjuntoTest(SimpleTestCase):
    def test_pdf_valido(self):
        validar_adjunto(SimpleUploadedFile("informe.pdf", b"%PDF-1.7\ncontenido"))

    def test_extension_no_permitida(self):
        with self.assertRaises(ValidationError):
            validar_adjunto(SimpleUploadedFile("programa.exe", b"MZ\x90\x00"))

    def test_contenido_no_coincide_con_extension(self):
        with self.assertRaises(ValidationError):
            validar_adjunto(SimpleUploadedFile("falso.pdf", b"<html>no soy un pdf</html>"))

    def test_imagenes(self):
        validar_adjunto(SimpleUploadedFile("foto.jpg", b"\xff\xd8\xff\xe0datos"))
        validar_adjunto(SimpleUploadedFile("foto.png", b"\x89PNG\r\n\x1a\ndatos"))

    def test_tamano_maximo_y_vacio(self):
        with self.assertRaises(ValidationError):
            validar_adjunto(SimpleUploadedFile("grande.pdf", b"%PDF-" + b"0" * (1024 * 1024 + 1)))
        with self.assertRaises(ValidationError):
            validar_adjunto(SimpleUploadedFile("vacio.pdf", b""))
