"""«Atención psicosocial» del prototipo v1: registrar atención (con borrador), resumen, fichas y estadísticas."""
import datetime

from django.urls import reverse
from django.utils import timezone

from apps.casos.models import Caso, SesionSeguimiento
from apps.casos.servicios import casos_urgentes

from .base import PruebaBase


class RegistrarAtencionTest(PruebaBase):
    def datos(self, **extra):
        return {"fecha": timezone.localdate().isoformat(), "hora": "00:00", "duracion_minutos": 45,
                "tipo_atencion": "individual", "urgencia": "media", "motivo": "regulacion_emocional",
                "derivado_por": "profesor_jefe", "nota": "Se conversa sobre cómo enfrentar los recreos.",
                "acuerdos": "Nueva sesión en dos semanas.", "accion": "registrar", **extra}

    def url(self, estudiante):
        return reverse("casos:registrar_atencion") + "?estudiante=%d" % estudiante.pk

    def test_abre_caso_de_seguimiento_si_no_hay(self):
        c = self.cliente(self.psicologa)
        r = c.post(self.url(self.estudiante), self.datos())
        caso = Caso.objects.get(estudiante=self.estudiante)
        self.assertRedirects(r, reverse("casos:detalle", args=[caso.pk]))
        self.assertEqual((caso.tipo_proceso, caso.responsable, caso.estado), ("seguimiento", self.psicologa, "seguimiento"))
        s = caso.sesiones.get()
        self.assertEqual((s.motivo, s.urgencia, s.acuerdos), ("regulacion_emocional", "media", "Nueva sesión en dos semanas."))

    def test_validaciones_y_borrador(self):
        c = self.cliente(self.psicologa)
        manana = (timezone.localdate() + datetime.timedelta(days=1)).isoformat()
        self.assertContains(c.post(self.url(self.estudiante), self.datos(fecha=manana)), "no puede quedar en el futuro")
        self.assertContains(c.post(self.url(self.estudiante), self.datos(nota="corta")), "al menos 10 caracteres")
        self.assertContains(c.post(self.url(self.estudiante), self.datos(motivo="")), "obligatorio")
        # Un borrador se guarda sin descripción y solo lo ve su autora.
        r = c.post(self.url(self.estudiante), self.datos(nota="", accion="borrador"))
        borrador = SesionSeguimiento.objects.get(estado="borrador")
        self.assertRedirects(r, reverse("casos:registrar_atencion") + "?borrador=%d" % borrador.pk)
        otra = self.cliente(self.psicologa2)
        self.assertEqual(otra.get(reverse("casos:registrar_atencion") + "?borrador=%d" % borrador.pk).status_code, 404)
        self.assertNotContains(otra.get(reverse("casos:detalle", args=[borrador.caso_id])), "borrador")
        # Al completarlo pasa a registrada.
        c.post(reverse("casos:registrar_atencion") + "?borrador=%d" % borrador.pk, self.datos())
        borrador.refresh_from_db()
        self.assertEqual(borrador.estado, "registrada")

    def test_elige_caso_si_hay_varios_y_no_admite_inactivos(self):
        Caso.objects.create(estudiante=self.estudiante, tipo_proceso="seguimiento", responsable=self.psicologa)
        pie = Caso.objects.create(estudiante=self.estudiante, tipo_proceso="pie_nee", responsable=self.pie)
        c = self.cliente(self.psicologa)
        self.assertContains(c.post(self.url(self.estudiante), self.datos()), "obligatorio")
        c.post(self.url(self.estudiante), self.datos(caso=pie.pk))
        self.assertEqual(pie.sesiones.count(), 1)
        self.estudiante2.fecha_egreso, self.estudiante2.tipo_salida = self.hoy - datetime.timedelta(days=1), "retiro"
        self.estudiante2.save()
        self.assertRedirects(c.get(self.url(self.estudiante2)), reverse("estudiantes:detalle", args=[self.estudiante2.pk]))

    def test_permisos(self):
        self.assertEqual(self.cliente(self.profesor).get(reverse("casos:registrar_atencion")).status_code, 403)
        self.assertEqual(self.cliente(self.pie).get(reverse("casos:registrar_atencion")).status_code, 403)


class ResumenTest(PruebaBase):
    def test_casos_urgentes_y_resumen(self):
        caso = Caso.objects.create(estudiante=self.estudiante, tipo_proceso="seguimiento", responsable=self.psicologa,
                                   fecha_apertura=self.hoy - datetime.timedelta(days=10))
        SesionSeguimiento.objects.create(caso=caso, profesional=self.psicologa, urgencia="alta",
                                         fecha_hora=timezone.now() - datetime.timedelta(days=5), nota="Sesión urgente.")
        self.assertEqual(casos_urgentes().count(), 1)
        SesionSeguimiento.objects.create(caso=caso, profesional=self.psicologa, urgencia="baja",
                                         fecha_hora=timezone.now() - datetime.timedelta(hours=1), nota="Ya más tranquila.")
        self.assertEqual(casos_urgentes().count(), 0)               # cuenta la urgencia de la última atención
        r = self.cliente(self.psicologa).get(reverse("casos:resumen"))
        self.assertContains(r, "Pendientes por prioridad")
        self.assertEqual(r.context["en_seguimiento"], 1)
        self.assertNotContains(r, "Sesión urgente")                 # el resumen no muestra contenido de sesiones
        self.assertEqual(self.cliente(self.directora).get(reverse("casos:resumen")).status_code, 200)
        self.assertEqual(self.cliente(self.profesor).get(reverse("casos:resumen")).status_code, 403)

    def test_estadisticas_de_atenciones_agregadas(self):
        caso = Caso.objects.create(estudiante=self.estudiante, tipo_proceso="seguimiento", responsable=self.psicologa)
        SesionSeguimiento.objects.create(caso=caso, profesional=self.psicologa, motivo="ansiedad", duracion_minutos=60,
                                         fecha_hora=timezone.now(), nota="Texto reservado de la atención.")
        r = self.cliente(self.directora).get(reverse("reportes:panel"))
        self.assertEqual(r.context["r"]["atenciones"]["total"], 1)
        self.assertEqual(r.context["r"]["atenciones"]["duracion_promedio"], 60)
        self.assertNotContains(r, "Texto reservado")
        self.assertNotContains(r, "Martina")

    def test_fichas_filtra_urgentes(self):
        caso = Caso.objects.create(estudiante=self.estudiante, tipo_proceso="seguimiento", responsable=self.psicologa)
        SesionSeguimiento.objects.create(caso=caso, profesional=self.psicologa, urgencia="alta", fecha_hora=timezone.now(),
                                         nota="Sesión urgente.")
        Caso.objects.create(estudiante=self.estudiante2, tipo_proceso="seguimiento", responsable=self.psicologa)
        r = self.cliente(self.psicologa).get(reverse("casos:lista") + "?estado=urgentes")
        self.assertEqual([c.pk for c in r.context["pagina"]], [caso.pk])
        self.assertContains(r, "URGENTE")
