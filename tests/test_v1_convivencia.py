"""Convivencia, protocolos, plan de gestión e indicadores (prototipo v1)."""
import datetime

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.alertas.models import AlertaRiesgo
from apps.casos import almacenamiento
from apps.convivencia.models import ActividadPlan, Anotacion, Conflicto, EvidenciaActividad, ProtocoloActivado, RegistroConductual
from apps.convivencia.servicios import anotaciones_por_curso, grafico_barras_apiladas

from .base import PruebaBase


class ConflictosAnotacionesTest(PruebaBase):
    def test_conflicto_con_acuerdo_exige_acuerdos(self):
        c = self.cliente(self.social)
        datos = {"fecha": self.hoy.isoformat(), "tipo_gestion": "mediacion", "curso": self.curso.pk,
                 "participantes": [self.estudiante.pk], "encargada": self.social.pk, "resultado": "con_acuerdo",
                 "descripcion": "Discusión en el recreo que terminó en empujones."}
        self.assertContains(c.post(reverse("convivencia:conflicto_nuevo"), datos), "Registre los acuerdos")
        datos["acuerdos"] = "Conversar con respeto."
        r = c.post(reverse("convivencia:conflicto_nuevo"), datos)
        conflicto = Conflicto.objects.get()
        self.assertRedirects(r, reverse("convivencia:conflicto", args=[conflicto.pk]))
        r = c.get(reverse("convivencia:conflictos"))
        self.assertEqual(r.context["por_tramo"], {"basica": 1, "media": 0})
        self.assertEqual(self.cliente(self.profesor).get(reverse("convivencia:conflictos")).status_code, 403)

    def test_profesor_jefe_anota_solo_en_su_curso(self):
        c = self.cliente(self.profesor)
        datos = {"fecha": self.hoy.isoformat(), "tipo": "positiva", "descripcion": "Ayuda a sus compañeros en clase."}
        r = c.post(reverse("convivencia:anotacion_nueva"), {**datos, "estudiante": self.estudiante2.pk})
        self.assertContains(r, "Escoja una opción válida")
        c.post(reverse("convivencia:anotacion_nueva"), {**datos, "estudiante": self.estudiante.pk})
        self.assertEqual(Anotacion.objects.get().registrada_por, self.profesor)
        Anotacion.objects.create(estudiante=self.estudiante2, tipo="grave", descripcion="Falta grave de otro curso.",
                                 registrada_por=self.social)
        r = c.get(reverse("convivencia:anotaciones"))
        self.assertEqual(r.context["total"], 1)                    # solo ve las de su curso
        r = self.cliente(self.social).get(reverse("convivencia:anotaciones"))
        self.assertEqual(r.context["total"], 2)

    def test_grafico_por_curso(self):
        Anotacion.objects.create(estudiante=self.estudiante, tipo="positiva", descripcion="Participa con entusiasmo.",
                                 registrada_por=self.social)
        filas = anotaciones_por_curso(Anotacion.objects.all())
        self.assertEqual(next(f for f in filas if f["nivel"] == "5B")["valores"], [1, 0, 0, 0])
        self.assertEqual(len(anotaciones_por_curso(Anotacion.objects.all(), "media")), 4)
        svg = grafico_barras_apiladas(filas)
        self.assertTrue(svg.startswith("<svg") and "5°B" in svg)


class SituacionConductualTest(PruebaBase):
    def test_porcentaje_solo_para_asistencia_y_aviso(self):
        with self.assertRaises(ValidationError):
            RegistroConductual(estudiante=self.estudiante, categoria="conductual", porcentaje_asistencia=80,
                               descripcion="Registro de prueba.", registrado_por=self.inspectora).full_clean()
        c = self.cliente(self.inspectora)
        r = c.post(reverse("convivencia:registro_nuevo"), {
            "estudiante": self.estudiante2.pk, "fecha": self.hoy.isoformat(), "categoria": "asistencia",
            "porcentaje_asistencia": "78", "descripcion": "Asistencia del semestre bajo lo esperado."}, follow=True)
        self.assertContains(r, "Inasistencia grave")
        self.assertEqual(RegistroConductual.objects.count(), 1)

    def test_descargas_excel(self):
        RegistroConductual.objects.create(estudiante=self.estudiante, categoria="atrasos", descripcion="Tres atrasos.",
                                          registrado_por=self.inspectora)
        c = self.cliente(self.social)
        for tipo in ("resumen", "detalle", "masiva"):
            r = c.get(reverse("convivencia:situacion_descargar") + "?tipo=" + tipo)
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.content.startswith(b"PK"))


class ProtocolosPlanTest(PruebaBase):
    def test_cierre_requiere_observaciones(self):
        p = ProtocoloActivado.objects.create(protocolo="accidente_escolar", curso=self.curso, responsable=self.social)
        c = self.cliente(self.social)
        url = reverse("convivencia:protocolo", args=[p.pk])
        self.assertContains(c.post(url, {"fecha_cierre": self.hoy.isoformat(), "observaciones": "Listo."}), "al menos 20")
        c.post(url, {"fecha_cierre": self.hoy.isoformat(), "observaciones": "Se informó a la familia y se activó el seguro."})
        p.refresh_from_db()
        self.assertEqual(p.estado, "cerrado")
        self.assertEqual(self.cliente(self.directora).post(url, {}).status_code, 403)    # la Directora solo consulta

    def test_estudiante_debe_pertenecer_al_curso(self):
        with self.assertRaises(ValidationError):
            ProtocoloActivado(protocolo="violencia", curso=self.curso, estudiante=self.estudiante2,
                              responsable=self.social).full_clean()

    def test_activar_protocolo_desde_la_alerta(self):
        alerta = AlertaRiesgo.objects.create(estudiante=self.estudiante, sede=self.sedes["Central"],
                                             tipo_situacion="conducta_suicida", informante=self.profesor,
                                             descripcion="Comenta en clases que no quiere seguir viviendo.",
                                             fecha_hora_conocimiento=timezone.now() - datetime.timedelta(hours=1))
        from apps.alertas.servicios import notificar_alerta
        notificar_alerta(alerta)
        self.cliente(self.psicologa).post(reverse("alertas:gestionar", args=[alerta.pk]), {
            "accion": "protocolo_activado", "detalle": "Se activa el protocolo del reglamento.",
            "fecha_hora": timezone.localtime().strftime("%Y-%m-%dT%H:%M")})
        p = ProtocoloActivado.objects.get(alerta=alerta)
        self.assertEqual((p.protocolo, p.estudiante, p.estado), ("conducta_suicida", self.estudiante, "abierto"))

    def test_actividad_realizada_y_evidencia_cifrada(self):
        with self.assertRaises(ValidationError):
            ActividadPlan(titulo="Taller de convivencia", fecha=self.hoy, responsable=self.social,
                          estado="realizada").full_clean()                  # falta el medio de verificación
        a = ActividadPlan.objects.create(titulo="Taller de convivencia", fecha=self.hoy, responsable=self.social,
                                         medio_verificacion="Lista de asistencia", estado="realizada")
        c = self.cliente(self.social)
        contenido = b"%PDF-1.7\nLista de asistencia del taller"
        c.post(reverse("convivencia:actividad", args=[a.pk]), {"archivo": SimpleUploadedFile("lista.pdf", contenido)})
        ev = EvidenciaActividad.objects.get()
        self.assertNotIn(b"Lista de asistencia", almacenamiento._ruta(ev.ruta_objeto).read_bytes())
        self.assertEqual(c.get(reverse("convivencia:evidencia", args=[ev.pk])).content, contenido)
        self.assertTrue(c.get(reverse("convivencia:plan_descargar")).content.startswith(b"PK"))


class IndicadoresTest(PruebaBase):
    def test_indice_de_bienestar(self):
        Anotacion.objects.create(estudiante=self.estudiante, tipo="gravisima", descripcion="Agresión en el recreo.",
                                 registrada_por=self.social)
        r = self.cliente(self.directora).get(reverse("convivencia:indicadores"))
        d = r.context["d"]
        self.assertEqual((d["total_activos"], d["con_senales"]), (2, 1))
        self.assertAlmostEqual(d["indice"], 50.0)
        self.assertNotContains(r, "Martina")
        self.assertEqual(self.cliente(self.profesor).get(reverse("convivencia:indicadores")).status_code, 403)
