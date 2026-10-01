"""Reportes agregados (RF-15) y API REST: solo cifras, acceso por permiso y segundo factor también en la API."""
import datetime
import json

from django.urls import reverse
from django.utils import timezone

from apps.casos.models import Caso, SesionSeguimiento

from .base import PruebaBase


class ReportesTest(PruebaBase):
    def setUp(self):
        self.caso = Caso.objects.create(estudiante=self.estudiante, tipo_proceso="seguimiento", responsable=self.psicologa,
                                        fecha_apertura=timezone.localdate() - datetime.timedelta(days=5))
        SesionSeguimiento.objects.create(caso=self.caso, profesional=self.psicologa, fecha_hora=timezone.now(),
                                         nota="Contenido clínico reservado de la sesión.")

    def test_panel_solo_para_perfiles_con_permiso(self):
        self.assertEqual(self.cliente(self.directora).get(reverse("reportes:panel")).status_code, 200)
        self.assertEqual(self.cliente(self.profesor).get(reverse("reportes:panel")).status_code, 403)

    def test_resumen_sin_datos_personales(self):
        r = self.cliente(self.directora).get(reverse("api:resumen"))
        self.assertEqual(r.status_code, 200)
        datos = json.loads(r.content)
        self.assertEqual(datos["casos_activos"], 1)
        texto = r.content.decode("utf-8")
        for dato in ("Martina", "Pérez", self.estudiante.rut, "Contenido clínico"):
            self.assertNotIn(dato, texto)

    def test_api_exige_segundo_factor(self):
        r = self.cliente(self.directora, mfa=False).get(reverse("api:resumen"))
        self.assertEqual(r.status_code, 403)
        self.assertIn("segundo factor", r.json()["detalle"])

    def test_linea_de_tiempo_respeta_el_acceso_al_caso(self):
        self.assertEqual(self.cliente(self.psicologa).get(reverse("api:linea_tiempo", args=[self.caso.pk])).status_code, 200)
        self.assertEqual(self.cliente(self.profesor).get(reverse("api:linea_tiempo", args=[self.caso.pk])).status_code, 403)
        self.assertEqual(self.cliente(self.admin).get(reverse("api:linea_tiempo", args=[self.caso.pk])).status_code, 403)
