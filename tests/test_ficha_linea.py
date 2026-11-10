"""La ficha del estudiante muestra una línea de tiempo única, con las reglas de acceso de cada caso."""
import datetime

from django.urls import reverse
from django.utils import timezone

from apps.casos.models import Caso, SesionSeguimiento

from .base import PruebaBase


class FichaLineaTiempoTest(PruebaBase):
    def setUp(self):
        self.caso = Caso.objects.create(estudiante=self.estudiante, tipo_proceso="seguimiento", responsable=self.psicologa,
                                        fecha_apertura=timezone.localdate() - datetime.timedelta(days=20))
        SesionSeguimiento.objects.create(caso=self.caso, profesional=self.psicologa, motivo="conducta",
                                         fecha_hora=timezone.now() - datetime.timedelta(days=5),
                                         nota="Nota de la sesión del equipo para la línea de tiempo.")
        SesionSeguimiento.objects.create(caso=self.caso, profesional=self.psicologa2, nivel_acceso="autora",
                                         motivo="ansiedad", fecha_hora=timezone.now() - datetime.timedelta(days=3),
                                         nota="Nota privada de otra psicóloga.")
        self.url = reverse("estudiantes:detalle", args=[self.estudiante.pk])

    def test_psicologa_ve_linea_con_sesiones_y_apertura(self):
        r = self.cliente(self.psicologa).get(self.url)
        self.assertContains(r, "Línea de tiempo")
        self.assertContains(r, "Nota de la sesión del equipo para la línea de tiempo.")
        self.assertContains(r, "Apertura del caso")
        self.assertNotContains(r, "Nota privada de otra psicóloga.")      # misma regla que en la ficha del caso

    def test_sin_registros(self):
        r = self.cliente(self.psicologa).get(reverse("estudiantes:detalle", args=[self.estudiante2.pk]))
        self.assertEqual(r.status_code, 200)
