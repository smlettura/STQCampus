"""Alertas de riesgo (RF-13, RF-14): enrutamiento según el reglamento interno, plazos, denuncia y constancias."""
import datetime

from django.core import mail
from django.core.exceptions import ValidationError
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from apps.alertas.models import AlertaRiesgo, Denuncia, GestionAlerta, Notificacion
from apps.alertas.servicios import notificar_alerta

from .base import PruebaBase


class EnrutamientoTest(PruebaBase):
    def crear(self, tipo, sede="Central", subtipo="", informante=None):
        a = AlertaRiesgo.objects.create(estudiante=self.estudiante, sede=self.sedes[sede], tipo_situacion=tipo,
                                        subtipo_violencia=subtipo, informante=informante or self.profesor,
                                        descripcion="Relato de los hechos observados en el patio.",
                                        fecha_hora_conocimiento=timezone.now() - datetime.timedelta(hours=1))
        notificar_alerta(a)
        return set(Notificacion.objects.filter(alerta=a, canal="plataforma").values_list("destinatario__correo", flat=True))

    def test_tabla_del_reglamento(self):
        self.assertEqual(self.crear("vulneracion_derechos"), {"psi@demo.cl", "psi2@demo.cl", "social@demo.cl"})
        self.assertEqual(self.crear("abuso_sexual"), {"social@demo.cl"})
        self.assertEqual(self.crear("alcohol_drogas_armas"), {"dir@demo.cl"})
        self.assertEqual(self.crear("conducta_suicida"), {"psi@demo.cl", "psi2@demo.cl"})
        self.assertEqual(self.crear("violencia_maltrato", subtipo="entre_adultos"), {"dir@demo.cl"})
        self.assertEqual(self.crear("violencia_maltrato", sede="Básica", subtipo="entre_estudiantes"), {"insp@demo.cl"})
        self.assertEqual(self.crear("violencia_maltrato", sede="Central", subtipo="adulto_a_estudiante"), {"social@demo.cl"})

    def test_quien_reporta_no_se_notifica_a_si_mismo(self):
        self.assertEqual(self.crear("conducta_suicida", informante=self.psicologa), {"psi2@demo.cl"})

    def test_correo_sin_datos_del_estudiante(self):
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.crear("abuso_sexual")
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("Martina", mail.outbox[0].body)
        self.assertNotIn("Pérez", mail.outbox[0].body)

    def test_constancia_detecta_alteracion(self):
        self.crear("abuso_sexual")
        n = Notificacion.objects.first()
        self.assertTrue(n.constancia_integra())
        with connection.cursor() as c:
            c.execute("UPDATE notificacion SET fecha_hora_envio = %s WHERE id_notificacion = %s",
                      [n.fecha_hora_envio - datetime.timedelta(hours=5), n.pk])
        n.refresh_from_db()
        self.assertFalse(n.constancia_integra())


class RegistroAlertaTest(PruebaBase):
    def post(self, **extra):
        datos = {"estudiante": self.estudiante.pk, "tipo_situacion": "violencia_maltrato", "subtipo_violencia": "",
                 "fecha_hora_conocimiento": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
                 "descripcion": "Durante el recreo se observa empujones reiterados.", **extra}
        return self.cliente(self.profesor).post(reverse("alertas:registrar"), datos)

    def test_validaciones(self):
        self.assertContains(self.post(), "entre quiénes ocurrió")
        futuro = (timezone.localtime() + datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        self.assertContains(self.post(subtipo_violencia="entre_estudiantes", fecha_hora_conocimiento=futuro), "futuro")
        self.assertContains(self.post(subtipo_violencia="entre_estudiantes", descripcion="corta"), "al menos 20")

    def test_registro_usa_sede_del_curso_y_muestra_constancia(self):
        r = self.post(subtipo_violencia="entre_estudiantes")
        alerta = AlertaRiesgo.objects.get()
        self.assertRedirects(r, reverse("alertas:constancia_registro", args=[alerta.pk]), fetch_redirect_response=False)
        self.assertEqual(alerta.sede, self.curso.sede)
        self.assertTrue(Notificacion.objects.filter(alerta=alerta, destinatario=self.social).exists())
        r = self.cliente(self.profesor).get(reverse("alertas:constancia_registro", args=[alerta.pk]))
        self.assertContains(r, Notificacion.objects.filter(alerta=alerta).first().hash_constancia)

    def test_acceso_restringido(self):
        self.post(subtipo_violencia="entre_estudiantes")
        alerta = AlertaRiesgo.objects.get()
        self.assertEqual(self.cliente(self.psicologa2).get(reverse("alertas:detalle", args=[alerta.pk])).status_code, 403)
        self.assertEqual(self.cliente(self.directora).get(reverse("alertas:detalle", args=[alerta.pk])).status_code, 200)


class DenunciaTest(PruebaBase):
    def setUp(self):
        self.alerta = AlertaRiesgo.objects.create(
            estudiante=self.estudiante, sede=self.sedes["Central"], tipo_situacion="abuso_sexual", posible_delito=True,
            descripcion="Relato de la estudiante sobre hechos ocurridos fuera del colegio.", informante=self.profesor,
            fecha_hora_conocimiento=timezone.now() - datetime.timedelta(hours=30))
        notificar_alerta(self.alerta)

    def test_solo_la_psicologa_designada(self):
        self.assertEqual(self.cliente(self.psicologa2).get(reverse("alertas:denunciar", args=[self.alerta.pk])).status_code, 403)
        with self.assertRaises(ValidationError):
            Denuncia(alerta=self.alerta, psicologa=self.psicologa2, institucion="pdi",
                     fecha_hora_presentacion=timezone.now()).full_clean(exclude=["directora_informada_en", "hash_constancia"])

    def test_fuera_de_plazo_exige_confirmacion(self):
        c = self.cliente(self.psicologa)
        datos = {"institucion": "ministerio_publico", "fecha_hora_presentacion": timezone.localtime().strftime("%Y-%m-%dT%H:%M")}
        self.assertContains(c.post(reverse("alertas:denunciar", args=[self.alerta.pk]), datos), "supera el plazo legal")
        c.post(reverse("alertas:denunciar", args=[self.alerta.pk]), {**datos, "fuera_de_plazo": "on"})
        d = Denuncia.objects.get()
        self.assertFalse(d.dentro_de_plazo)
        self.assertTrue(d.constancia_integra())
        self.alerta.refresh_from_db()
        self.assertEqual(self.alerta.estado, "denunciada")
        self.assertTrue(Notificacion.objects.filter(alerta=self.alerta, destinatario=self.directora).exists())

    def test_no_se_cierra_sin_protocolo_ni_denuncia(self):
        g = GestionAlerta(alerta=self.alerta, responsable=self.social, accion="cierre", detalle="Se cierra la situación.")
        with self.assertRaises(ValidationError) as ctx:
            g.full_clean()
        self.assertIn("protocolo", str(ctx.exception))
        GestionAlerta.objects.create(alerta=self.alerta, responsable=self.social, accion="protocolo_activado",
                                     detalle="Se activa el protocolo del reglamento.")
        with self.assertRaises(ValidationError) as ctx:
            g.full_clean()
        self.assertIn("denuncia", str(ctx.exception))
