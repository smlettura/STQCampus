"""Módulo de IA reservado (en entrenamiento) y cumplimiento (RF-11, RF-12, RNF-10, RNF-13)."""
import datetime
import json

from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.auditoria.models import EventoAuditoria
from apps.casos.models import Caso, SesionSeguimiento
from apps.core.validadores import sumar_anios
from apps.cumplimiento import servicios as cumplimiento
from apps.cumplimiento.models import Consentimiento, RetencionEliminacion, SolicitudARCO
from apps.estudiantes.models import Estudiante
from apps.ia import servicios as ia

from .base import PruebaBase


class ModuloIAReservadoTest(PruebaBase):
    """La IA está en entrenamiento: la pantalla existe con datos reales, pero no genera nada (espacio reservado)."""

    def setUp(self):
        self.caso = Caso.objects.create(estudiante=self.estudiante, tipo_proceso="seguimiento", responsable=self.psicologa,
                                        fecha_apertura=timezone.localdate() - datetime.timedelta(days=20))
        SesionSeguimiento.objects.create(caso=self.caso, profesional=self.psicologa,
                                         fecha_hora=timezone.now() - datetime.timedelta(days=10), motivo="conducta",
                                         nota="Contenido reservado de la sesión de Martina.")
        SesionSeguimiento.objects.create(caso=self.caso, profesional=self.psicologa2, nivel_acceso="autora",
                                         fecha_hora=timezone.now() - datetime.timedelta(days=5), motivo="ansiedad",
                                         nota="Nota privada de otra psicóloga.")

    def test_servicio_no_genera(self):
        self.assertFalse(ia.DISPONIBLE)
        with self.assertRaises(ia.ModuloIANoDisponible):
            ia.generar_borrador(estudiante=self.estudiante, sesiones=[], tipo="atencion", secciones=[],
                                usuario=self.psicologa)

    def test_pantalla_muestra_atenciones_sin_notas_y_boton_deshabilitado(self):
        url = reverse("ia:generar_informe") + "?estudiante=%d" % self.estudiante.pk
        r = self.cliente(self.psicologa).get(url)
        self.assertContains(r, "EN ENTRENAMIENTO")
        self.assertContains(r, "Conducta en aula")                    # la atención propia del equipo se lista
        self.assertNotContains(r, "Contenido reservado")              # nunca el texto de la sesión
        self.assertNotContains(r, "Ansiedad o estrés")                # ni la sesión privada de otra profesional
        self.assertRegex(r.content.decode(), r'<button class="boton boton-generar" type="button" disabled')
        self.assertTrue(EventoAuditoria.objects.filter(entidad="estudiante", id_entidad=self.estudiante.pk,
                                                       detalle__contains="generar informe").exists())
        self.assertEqual(self.cliente(self.psicologa).post(url).status_code, 405)

    def test_solo_equipo_psicosocial(self):
        url = reverse("ia:generar_informe")
        self.assertEqual(self.cliente(self.pie).get(url).status_code, 403)
        self.assertEqual(self.cliente(self.profesor).get(url).status_code, 403)
        self.assertEqual(self.cliente(self.directora).get(url).status_code, 403)


class ConsentimientoArcoTest(PruebaBase):
    def test_apoderado_debe_estar_vinculado(self):
        otro = self.estudiante2.apoderado_titular()
        with self.assertRaises(ValidationError):
            Consentimiento(estudiante=self.estudiante, apoderado=otro, alcance="seguimiento",
                           fecha_otorgamiento=timezone.localdate()).full_clean()

    def test_revocacion_no_anterior_y_vigencia(self):
        c = Consentimiento.objects.create(estudiante=self.estudiante, apoderado=self.apoderado, alcance="seguimiento",
                                          fecha_otorgamiento=timezone.localdate() - datetime.timedelta(days=5))
        c.fecha_revocacion = c.fecha_otorgamiento - datetime.timedelta(days=1)
        with self.assertRaises(ValidationError):
            c.full_clean()
        self.assertTrue(Consentimiento.vigente_para(self.estudiante, "seguimiento"))

    def test_arco_calcula_plazo_y_exporta_sin_contenido_clinico(self):
        cli = self.cliente(self.admin)
        cli.post(reverse("cumplimiento:arco_nueva", args=[self.estudiante.pk]),
                 {"apoderado": self.apoderado.pk, "tipo_derecho": "portabilidad",
                  "fecha_recepcion": timezone.localdate().isoformat()})
        s = SolicitudARCO.objects.get()
        self.assertEqual(s.fecha_limite, s.fecha_recepcion + datetime.timedelta(days=30))
        caso = Caso.objects.create(estudiante=self.estudiante, tipo_proceso="seguimiento", responsable=self.psicologa)
        SesionSeguimiento.objects.create(caso=caso, profesional=self.psicologa, fecha_hora=timezone.now(),
                                         nota="Contenido clínico de la sesión")
        datos = json.loads(cli.get(reverse("cumplimiento:arco_exportar", args=[s.pk])).content)
        self.assertEqual(datos["estudiante"]["rut"], self.estudiante.rut)
        self.assertNotIn("atenciones", datos["casos"][0])
        self.assertTrue(EventoAuditoria.objects.filter(accion="exportacion", entidad="estudiante").exists())


class RetencionTest(PruebaBase):
    def setUp(self):
        self.antiguo = Estudiante.objects.create(rut="19876543-0", primer_nombre="Ignacio", apellido_paterno="Valdés",
                                                 apellido_materno="Ortiz", fecha_nacimiento=datetime.date(1996, 5, 5),
                                                 curso=self.curso, fecha_egreso=sumar_anios(timezone.localdate(), -16),
                                                 tipo_salida="egreso")
        Caso.objects.create(estudiante=self.antiguo, tipo_proceso="seguimiento", responsable=self.psicologa,
                            estado="cerrado", fecha_apertura=sumar_anios(timezone.localdate(), -17),
                            fecha_cierre=sumar_anios(timezone.localdate(), -16))

    def test_propone_solo_con_plazo_cumplido_y_sin_duplicar(self):
        self.assertEqual(cumplimiento.proponer_retenciones(), 1)
        self.assertEqual(cumplimiento.proponer_retenciones(), 0)
        self.assertEqual(RetencionEliminacion.objects.get().estudiante, self.antiguo)

    def test_solo_la_directora_autoriza_y_se_anonimiza(self):
        cumplimiento.proponer_retenciones()
        r = RetencionEliminacion.objects.get()
        with self.assertRaises(ValidationError):
            cumplimiento.autorizar(r, self.admin, "anonimizar")
        r.refresh_from_db()
        with self.assertRaises(PermissionError):
            cumplimiento.ejecutar(r)
        cli = self.cliente(self.directora)
        cli.post(reverse("cumplimiento:retencion_decidir", args=[r.pk]), {"accion": "anonimizar", "decision": "autorizar"})
        r.refresh_from_db()
        self.assertEqual(r.estado, "propuesta")            # falta la confirmación de revisión
        cli.post(reverse("cumplimiento:retencion_decidir", args=[r.pk]),
                 {"accion": "anonimizar", "decision": "autorizar", "confirmar": "on"})
        r.refresh_from_db()
        self.assertEqual((r.estado, r.autorizada_por), ("autorizada", self.directora))
        cumplimiento.ejecutar(r)
        self.antiguo.refresh_from_db()
        self.assertEqual(self.antiguo.nombres, "Registro")
        self.assertEqual(self.antiguo.apellido_paterno, "anonimizado")
        self.assertTrue(self.antiguo.rut.startswith("ANON-"))
        self.assertFalse(self.antiguo.vinculos_apoderado.exists())
