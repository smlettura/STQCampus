"""Listas desplegables de los buscadores: solo devuelven lo que el usuario ya puede ver."""
import datetime

from django.urls import reverse
from django.utils import timezone

from apps.casos.models import Caso

from .base import PruebaBase


class SugerenciasTest(PruebaBase):
    def test_estudiantes_coinciden_y_requieren_dos_letras(self):
        url = reverse("estudiantes:sugerencias")
        cli = self.cliente(self.psicologa)
        self.assertEqual(cli.get(url, {"q": "m"}).json(), {"resultados": []})
        datos = cli.get(url, {"q": self.estudiante.primer_nombre[:3]}).json()["resultados"]
        self.assertIn(self.estudiante.pk, [r["id"] for r in datos])
        r = next(r for r in datos if r["id"] == self.estudiante.pk)
        self.assertEqual(r["url"], reverse("estudiantes:detalle", args=[self.estudiante.pk]))

    def test_estudiantes_sin_sesion(self):
        r = self.client.get(reverse("estudiantes:sugerencias"), {"q": "ma"})
        self.assertNotEqual(r.status_code, 200)                      # sin sesión no responde datos

    def test_casos_solo_visibles(self):
        Caso.objects.create(estudiante=self.estudiante, tipo_proceso="seguimiento", responsable=self.psicologa,
                            fecha_apertura=timezone.localdate() - datetime.timedelta(days=3))
        datos = self.cliente(self.psicologa).get(reverse("casos:sugerencias"), {"q": self.estudiante.primer_nombre}).json()
        self.assertEqual(len(datos["resultados"]), 1)
        self.assertEqual(self.cliente(self.profesor).get(reverse("casos:sugerencias"), {"q": "ma"}).status_code, 403)

    def test_usuarios_solo_administracion(self):
        url = reverse("cuentas:usuarios_sugerencias")
        self.assertEqual(self.cliente(self.psicologa).get(url, {"q": "ca"}).status_code, 403)
        datos = self.cliente(self.admin).get(url, {"q": "Andrés"}).json()["resultados"]
        self.assertEqual([r["id"] for r in datos], [self.admin.pk])
