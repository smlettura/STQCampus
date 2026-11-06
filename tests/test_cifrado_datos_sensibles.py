"""Datos sensibles (Ley 21.719): catálogo de columnas cifradas, migración que cifra en su lugar y mensajes fuera de cookies."""
import io
from types import SimpleNamespace

from django.apps import apps
from django.conf import settings
from django.core.management import CommandError, call_command
from django.db import connection
from django.urls import reverse

from apps.convivencia.models import Anotacion, RegistroConductual
from apps.core.campos import TextoCifrado
from apps.core.migraciones import cifrar_columna
from apps.evaluacion.forms import EvaluacionForm

from .base import PruebaBase

# Toda columna de texto libre que puede contener datos de salud, de conducta o de la vida privada de un estudiante.
COLUMNAS_CIFRADAS = {
    ("cuentas", "Usuario", "secreto_totp"),
    ("casos", "Derivacion", "motivo"), ("casos", "SesionSeguimiento", "nota"), ("casos", "SesionSeguimiento", "acuerdos"),
    ("casos", "Hito", "descripcion"), ("casos", "Documento", "nombre_archivo"),
    ("evaluacion", "EvaluacionDiagnostica", "tipo_nee"), ("evaluacion", "EvaluacionDiagnostica", "diagnostico"),
    ("evaluacion", "ParticipacionEvaluacion", "aporte"), ("evaluacion", "PlanApoyo", "adecuaciones"),
    ("evaluacion", "PlanApoyo", "detalle"), ("evaluacion", "Informe", "contenido"),
    ("ia", "ContenidoIA", "texto_generado"), ("ia", "RetroalimentacionIA", "comentario"),
    ("convivencia", "Conflicto", "descripcion"), ("convivencia", "Conflicto", "acuerdos"),
    ("convivencia", "Anotacion", "descripcion"), ("convivencia", "RegistroConductual", "descripcion"),
    ("convivencia", "ProtocoloActivado", "observaciones"), ("convivencia", "EvidenciaActividad", "nombre_archivo"),
    ("alertas", "AlertaRiesgo", "descripcion"), ("alertas", "GestionAlerta", "detalle"),
}


def crudo(tabla, columna, pk, id_fila):
    with connection.cursor() as c:
        c.execute("SELECT %s FROM %s WHERE %s = %%s" % (columna, tabla, pk), [id_fila])
        valor = c.fetchone()[0]
    return valor if isinstance(valor, str) else bytes(valor)


class CatalogoTest(PruebaBase):
    def test_columnas_sensibles_cifradas(self):
        for app, modelo, campo in COLUMNAS_CIFRADAS:
            with self.subTest(columna="%s.%s" % (modelo, campo)):
                self.assertIsInstance(apps.get_model(app, modelo)._meta.get_field(campo), TextoCifrado)

    def test_anotacion_y_registro_conductual_se_guardan_cifrados(self):
        a = Anotacion.objects.create(estudiante=self.estudiante, tipo="grave", registrada_por=self.psicologa,
                                     descripcion="Empuja a un compañero durante el recreo")
        r = RegistroConductual.objects.create(estudiante=self.estudiante, categoria="conductual",
                                              registrado_por=self.psicologa, descripcion="Dificultad para respetar turnos")
        self.assertNotIn(b"recreo", crudo("anotacion", "descripcion", "id_anotacion", a.pk))
        self.assertNotIn(b"turnos", crudo("registro_conductual", "descripcion", "id_registro", r.pk))
        self.assertEqual(Anotacion.objects.get(pk=a.pk).descripcion, "Empuja a un compañero durante el recreo")

    def test_tipo_nee_es_una_linea_de_80_caracteres(self):
        campo = EvaluacionForm(caso=None).fields["tipo_nee"]
        self.assertEqual((campo.max_length, campo.widget.input_type), (80, "text"))


class MigracionCifradoTest(PruebaBase):
    def test_cifra_en_su_lugar_es_idempotente_y_reversible(self):
        a = Anotacion.objects.create(estudiante=self.estudiante, tipo="moderada", registrada_por=self.psicologa,
                                     descripcion="temporal para la prueba")
        with connection.cursor() as c:                       # simula una fila escrita antes de la migración
            c.execute("UPDATE anotacion SET descripcion = %s WHERE id_anotacion = %s", ["No trae materiales", a.pk])
        op = cifrar_columna("anotacion", "descripcion", "id_anotacion")
        editor = SimpleNamespace(connection=connection)
        op.code(apps, editor)
        cifrado = crudo("anotacion", "descripcion", "id_anotacion", a.pk)
        self.assertTrue(cifrado.startswith(b"\x01"))
        self.assertNotIn(b"materiales", cifrado)
        self.assertEqual(Anotacion.objects.get(pk=a.pk).descripcion, "No trae materiales")
        op.code(apps, editor)                                # segunda pasada: no vuelve a cifrar
        self.assertEqual(crudo("anotacion", "descripcion", "id_anotacion", a.pk), cifrado)
        op.reverse_code(apps, editor)
        plano = crudo("anotacion", "descripcion", "id_anotacion", a.pk)
        self.assertEqual(plano if isinstance(plano, str) else plano.decode(), "No trae materiales")


class MensajesTest(PruebaBase):
    def test_los_mensajes_con_nombres_no_viajan_en_cookies(self):
        self.assertTrue(settings.MESSAGE_STORAGE.endswith("SessionStorage"))
        r = self.cliente(self.psicologa).post(reverse("estudiantes:inactivar", args=[self.estudiante2.pk]),
                                              {"fecha_retiro": self.hoy.isoformat(), "confirmar": "on"})
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("messages", r.cookies)


class ComandoVerificarCifradoTest(PruebaBase):
    def test_detecta_texto_plano_sin_mostrar_datos(self):
        a = Anotacion.objects.create(estudiante=self.estudiante, tipo="moderada", registrada_por=self.psicologa,
                                     descripcion="Llega tarde a clases")
        salida = io.StringIO()
        call_command("verificar_cifrado", stdout=salida)
        self.assertIn("sin problemas", salida.getvalue())
        with connection.cursor() as c:                       # alguien escribe texto plano directo en la base
            c.execute("UPDATE anotacion SET descripcion = %s WHERE id_anotacion = %s", ["Llega tarde a clases", a.pk])
        salida = io.StringIO()
        with self.assertRaises(CommandError):
            call_command("verificar_cifrado", stdout=salida)
        self.assertIn("anotacion.descripcion", salida.getvalue())
        self.assertNotIn("Llega tarde", salida.getvalue())
