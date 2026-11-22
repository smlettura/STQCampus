"""Modo privado (ocultar y mostrar datos sensibles con un clic), avisos modernos y panel ARCO+ completo."""
import datetime

from django.urls import reverse
from django.utils import timezone

from apps.auditoria.models import EventoAuditoria
from apps.core import privacidad
from apps.cumplimiento import servicios as cumplimiento
from apps.cumplimiento.models import (AccionARCO, BloqueoTratamiento, Consentimiento, RetencionEliminacion,
                                      SolicitudARCO)
from apps.estudiantes.models import Estudiante

from .base import CLAVE, PruebaBase


class ModoPrivadoTest(PruebaBase):
    def setUp(self):
        self.cli = self.cliente(self.psicologa)
        self.ficha = reverse("estudiantes:detalle", args=[self.estudiante.pk])

    def ocultar(self):
        return self.cli.post(reverse("cuentas:privacidad_ocultar"), {"next": self.ficha})

    def test_enmascaramiento(self):
        self.assertEqual(privacidad.iniciales("Martina Pérez Lagos"), "M. P. L.")
        self.assertEqual(privacidad.enmascarar("24512331-5", "rut"), privacidad.OCULTO_RUT)
        self.assertEqual(privacidad.enmascarar("", "texto"), "")

    def test_ocultar_y_volver_a_mostrar_con_un_clic(self):
        r = self.cli.get(self.ficha)
        self.assertContains(r, "Martina")
        self.assertContains(r, 'aria-label="Ocultar datos sensibles"')
        self.assertRedirects(self.ocultar(), self.ficha)
        r = self.cli.get(self.ficha)
        self.assertNotContains(r, "Martina")
        self.assertNotContains(r, "Lagos")
        self.assertContains(r, "M. P.")
        self.assertContains(r, "Modo privado.")
        self.assertContains(r, privacidad.OCULTO_RUT)
        url = reverse("cuentas:privacidad_mostrar")
        self.assertEqual(self.cli.get(url).status_code, 405)           # solo por POST (con token CSRF)
        self.assertRedirects(self.cli.post(url, {"next": self.ficha}), self.ficha)
        self.assertContains(self.cli.get(self.ficha), "Martina")
        detalles = list(EventoAuditoria.objects.filter(entidad="sesion").values_list("detalle", flat=True))
        self.assertIn("modo privado activado", detalles)
        self.assertIn("modo privado desactivado", detalles)

    def test_sugerencias_y_listas_ocultas(self):
        self.ocultar()
        datos = self.cli.get(reverse("estudiantes:sugerencias"), {"q": "Martina"}).json()["resultados"]
        self.assertEqual(datos[0]["texto"], "M. P. L.")
        self.assertNotIn(self.estudiante.rut[:4], datos[0]["detalle"])
        self.assertNotContains(self.cli.get(reverse("estudiantes:lista")), "Martina")

    def test_pantallas_de_edicion_desactivan_el_modo_privado(self):
        editar = reverse("estudiantes:editar", args=[self.estudiante.pk])
        self.ocultar()
        r = self.cli.get(editar)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Modo privado desactivado")
        self.assertContains(self.cli.get(self.ficha), "Martina")

    def test_los_datos_reales_no_cambian(self):
        """El modo privado solo afecta la presentación: la seudonimización del copiloto sigue usando el nombre real."""
        self.ocultar()
        self.cli.get(self.ficha)
        e = Estudiante.objects.get(pk=self.estudiante.pk)
        self.assertEqual(e.nombres, "Martina")


class AvisosModernosTest(PruebaBase):
    def test_mensajes_como_avisos_flotantes(self):
        cli = self.cliente(self.psicologa)
        r = cli.post(reverse("cuentas:privacidad_ocultar"), follow=True)
        self.assertContains(r, 'class="toast info"')
        self.assertContains(r, 'class="toast-cerrar"')

    def test_acciones_destructivas_marcadas_como_peligro(self):
        r = self.cliente(self.admin).get(reverse("estudiantes:detalle", args=[self.estudiante.pk]))
        self.assertContains(r, 'data-confirmar="¿Desvincular a este apoderado?" data-peligro')


class PanelArcoTest(PruebaBase):
    def solicitud(self, derecho, **extra):
        cli = self.cliente(self.psicologa)
        r = cli.post(reverse("cumplimiento:arco_nueva", args=[self.estudiante.pk]),
                     {"apoderado": self.apoderado.pk, "tipo_derecho": derecho,
                      "fecha_recepcion": timezone.localdate().isoformat(), "detalle": "Detalle de prueba", **extra})
        s = SolicitudARCO.objects.latest("pk")
        self.assertRedirects(r, reverse("cumplimiento:arco_detalle", args=[s.pk]))
        return cli, s

    def test_panel_con_indicadores_filtros_y_nueva_solicitud(self):
        cli, s = self.solicitud("acceso")
        SolicitudARCO.objects.filter(pk=s.pk).update(fecha_recepcion=timezone.localdate() - datetime.timedelta(days=40),
                                                     fecha_limite=timezone.localdate() - datetime.timedelta(days=10))
        r = cli.get(reverse("cumplimiento:arco"))
        self.assertEqual(r.context["kpis"]["vencidas"], 1)
        self.assertContains(r, "Nueva solicitud")
        self.assertEqual(len(cli.get(reverse("cumplimiento:arco"), {"derecho": "supresion"}).context["solicitudes"]), 0)
        self.assertEqual(len(cli.get(reverse("cumplimiento:arco"), {"q": "Martina"}).context["solicitudes"]), 1)
        self.assertRedirects(cli.get(reverse("cumplimiento:arco_buscar"), {"estudiante": self.estudiante.pk}),
                             reverse("cumplimiento:arco_nueva", args=[self.estudiante.pk]))
        self.assertEqual(AccionARCO.objects.get(solicitud=s).tipo, "registro")

    def test_acceso_informe_imprimible(self):
        cli, s = self.solicitud("acceso")
        r = cli.get(reverse("cumplimiento:arco_acceso", args=[s.pk]))
        self.assertContains(r, "Informe de acceso a datos personales")
        self.assertContains(r, "Martina")
        s.refresh_from_db()
        self.assertEqual(s.estado, "en_analisis")
        self.assertTrue(s.acciones.filter(tipo="informe_acceso").exists())
        self.assertTrue(EventoAuditoria.objects.filter(accion="exportacion", detalle__contains="informe de acceso").exists())

    def test_rectificacion_registra_solo_los_campos(self):
        cli, s = self.solicitud("rectificacion")
        url = reverse("cumplimiento:arco_rectificar", args=[s.pk])
        e = self.estudiante
        datos = {"rut": e.rut, "primer_nombre": "Martina", "segundo_nombre": "", "apellido_paterno": "Pérez",
                 "apellido_materno": "Larraín", "nombre_social": "", "fecha_nacimiento": e.fecha_nacimiento.isoformat(),
                 "apo-nombre_completo": self.apoderado.nombre_completo, "apo-telefono": "+56998887766",
                 "apo-correo": self.apoderado.correo}
        self.assertRedirects(cli.post(url, datos), reverse("cumplimiento:arco_detalle", args=[s.pk]))
        e.refresh_from_db()
        self.assertEqual(e.apellido_materno, "Larraín")
        accion = s.acciones.get(tipo="rectificacion")
        self.assertIn("estudiante.apellido_materno", accion.detalle)
        self.assertIn("apoderado.telefono", accion.detalle)
        self.assertNotIn("Larraín", accion.detalle)
        self.assertFalse(EventoAuditoria.objects.filter(detalle__contains="Larraín").exists())

    def test_accion_que_no_corresponde_al_derecho(self):
        cli, s = self.solicitud("acceso")
        r = cli.get(reverse("cumplimiento:arco_rectificar", args=[s.pk]))
        self.assertRedirects(r, reverse("cumplimiento:arco_detalle", args=[s.pk]))
        self.assertFalse(s.acciones.filter(tipo="rectificacion").exists())

    def test_supresion_se_propone_y_la_autoriza_la_directora(self):
        cli, s = self.solicitud("supresion")
        url = reverse("cumplimiento:arco_suprimir", args=[s.pk])
        cli.post(url, {"accion": "anonimizar"})                # sin confirmar la revisión: no se propone
        self.assertFalse(RetencionEliminacion.objects.exists())
        cli.post(url, {"accion": "anonimizar", "confirmar": "on"})
        r = RetencionEliminacion.objects.get()
        self.assertEqual((r.origen, r.solicitud_arco, r.estado), ("arco", s, "propuesta"))
        cumplimiento.autorizar(r, self.directora, "anonimizar")
        r.refresh_from_db()
        self.assertEqual(r.estado, "autorizada")
        cli.post(url, {"accion": "eliminar", "confirmar": "on"})  # no se duplica
        self.assertEqual(RetencionEliminacion.objects.count(), 1)

    def test_oposicion_revoca_el_consentimiento(self):
        self.consentir(self.estudiante, "uso_ia", "seguimiento")
        cli, s = self.solicitud("oposicion")
        cli.post(reverse("cumplimiento:arco_oponerse", args=[s.pk]), {"alcances": ["uso_ia"]})
        self.assertFalse(Consentimiento.vigente_para(self.estudiante, "uso_ia"))
        self.assertTrue(Consentimiento.vigente_para(self.estudiante, "seguimiento"))
        self.assertIn("uso_ia", s.acciones.get(tipo="oposicion").detalle)

    def test_bloqueo_suspende_el_tratamiento(self):
        self.consentir(self.estudiante, "uso_ia")
        from apps.casos.models import Caso
        Caso.objects.create(estudiante=self.estudiante, tipo_proceso="seguimiento", responsable=self.psicologa)
        cli, s = self.solicitud("bloqueo")
        cli.post(reverse("cumplimiento:arco_bloquear", args=[s.pk]), {"motivo": "Mientras se resuelve el reclamo"})
        self.assertTrue(BloqueoTratamiento.activo_para(self.estudiante))
        self.assertFalse(Consentimiento.vigente_para(self.estudiante, "uso_ia"))
        r = cli.get(reverse("ia:generar_informe"), {"estudiante": self.estudiante.pk})
        self.assertContains(r, "está bloqueado por una solicitud ARCO+")
        self.assertContains(cli.get(reverse("estudiantes:detalle", args=[self.estudiante.pk])), "Tratamiento bloqueado")
        cli.post(reverse("cumplimiento:arco_desbloquear", args=[s.pk]))
        self.assertFalse(BloqueoTratamiento.activo_para(self.estudiante))
        self.assertTrue(Consentimiento.vigente_para(self.estudiante, "uso_ia"))

    def test_respuesta_exige_texto_y_habilita_la_carta(self):
        cli, s = self.solicitud("portabilidad")
        url = reverse("cumplimiento:arco_detalle", args=[s.pk])
        hoy = timezone.localdate().isoformat()
        r = cli.post(url, {"estado": "respondida", "fecha_respuesta": hoy, "respuesta": ""})
        self.assertContains(r, "Escriba la respuesta")
        self.assertRedirects(cli.get(reverse("cumplimiento:arco_carta", args=[s.pk])), url)
        cli.post(url, {"estado": "respondida", "fecha_respuesta": hoy, "respuesta": "Adjuntamos el expediente en JSON."})
        s.refresh_from_db()
        self.assertEqual(s.estado, "respondida")
        r = cli.get(reverse("cumplimiento:arco_carta", args=[s.pk]))
        self.assertContains(r, "Adjuntamos el expediente en JSON.")
        self.assertContains(r, "acogida")
        # Cerrada: ya no se pueden ejecutar acciones.
        self.assertEqual(cli.post(reverse("cumplimiento:arco_bloquear", args=[s.pk]), {"motivo": "x"}).status_code, 302)
        self.assertFalse(BloqueoTratamiento.objects.exists())

    def test_solo_quien_gestiona_arco(self):
        _, s = self.solicitud("acceso")
        for u in (self.profesor, self.pie):
            self.assertEqual(self.cliente(u).get(reverse("cumplimiento:arco_detalle", args=[s.pk])).status_code, 403)
            self.assertEqual(self.cliente(u).post(reverse("cumplimiento:arco_bloquear", args=[s.pk]),
                                                  {"motivo": "x"}).status_code, 403)
