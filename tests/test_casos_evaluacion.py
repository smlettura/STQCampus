"""Gestión de casos (RF-01 a RF-04) y evaluación diagnóstica, planes e informes (RF-05 a RF-08)."""
import datetime

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.casos import almacenamiento
from apps.casos.models import Caso, Derivacion, Documento, SesionSeguimiento
from apps.estudiantes.models import Estudiante, EstudianteApoderado
from apps.evaluacion.models import AvisoReevaluacion, EvaluacionDiagnostica, Informe, ParticipacionEvaluacion, PlanApoyo
from apps.evaluacion.servicios import procesar_reevaluaciones

from .base import PruebaBase, rut


class FichaTest(PruebaBase):
    def test_crear_ficha_valida_rut_y_edad(self):
        c = self.cliente(self.admin)
        datos = {"rut": "12.345.678-9", "primer_nombre": "Ana", "apellido_paterno": "Gómez", "apellido_materno": "Paz",
                 "fecha_nacimiento": "2016-04-10", "curso": self.curso.pk, "necesidad_educativa": "ninguna",
                 "apo-parentesco": "madre"}
        r = c.post(reverse("estudiantes:crear"), datos)
        self.assertContains(r, "dígito verificador")
        datos["rut"] = "12.345.678-5"
        datos["fecha_nacimiento"] = "1970-01-01"
        self.assertContains(c.post(reverse("estudiantes:crear"), datos), "no corresponde a un estudiante escolar")
        datos["fecha_nacimiento"] = "2016-04-10"
        datos["en_pie"] = "on"
        self.assertContains(c.post(reverse("estudiantes:crear"), datos), "necesidad educativa transitoria o permanente")
        del datos["en_pie"]
        r = c.post(reverse("estudiantes:crear"), datos)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Estudiante.objects.get(primer_nombre="Ana").rut, "12345678-5")

    def test_un_solo_apoderado_titular(self):
        c = self.cliente(self.admin)
        r = c.post(reverse("estudiantes:vincular_apoderado", args=[self.estudiante.pk]),
                   {"rut": rut(9_876_543), "nombre_completo": "Luis Pérez", "telefono": "912345678",
                    "parentesco": "padre", "es_titular": "on"})
        self.assertContains(r, "ya tiene un apoderado titular")
        r = c.post(reverse("estudiantes:vincular_apoderado", args=[self.estudiante.pk]),
                   {"rut": rut(9_876_543), "nombre_completo": "Luis Pérez", "telefono": "912345678", "parentesco": "padre"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(EstudianteApoderado.objects.filter(estudiante=self.estudiante).count(), 2)


class DerivacionCasoTest(PruebaBase):
    def test_derivacion_valida_y_duplicada(self):
        c = self.cliente(self.profesor)
        base = {"estudiante": self.estudiante.pk, "fecha_hora": timezone.localtime().strftime("%Y-%m-%dT%H:%M")}
        self.assertContains(c.post(reverse("casos:derivar"), {**base, "motivo": "muy corto"}), "al menos 20 caracteres")
        futuro = (timezone.localtime() + datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        self.assertContains(c.post(reverse("casos:derivar"), {**base, "fecha_hora": futuro,
                                                              "motivo": "Se observa aislamiento en recreos."}), "futuro")
        r = c.post(reverse("casos:derivar"), {**base, "motivo": "Se observa aislamiento en recreos."})
        self.assertEqual(r.status_code, 302)
        self.assertContains(c.post(reverse("casos:derivar"), {**base, "motivo": "Otra vez, aislamiento en recreos."}),
                            "derivación pendiente")

    def test_abrir_caso_desde_derivacion(self):
        d = Derivacion.objects.create(estudiante=self.estudiante, derivante=self.profesor,
                                      motivo="Se observa aislamiento en recreos y baja participación.")
        c = self.cliente(self.psicologa)
        antes = (timezone.localdate() - datetime.timedelta(days=5)).isoformat()
        datos = {"tipo_proceso": "seguimiento", "responsable": self.profesor.pk, "fecha_apertura": antes}
        r = c.post(reverse("casos:abrir", args=[d.pk]), datos)
        self.assertContains(r, "antes de la derivación")
        self.assertContains(r, "Escoja una opción válida")      # el profesor jefe no puede ser responsable
        datos.update(responsable=self.psicologa.pk, fecha_apertura=timezone.localdate().isoformat())
        r = c.post(reverse("casos:abrir", args=[d.pk]), datos)
        d.refresh_from_db()
        self.assertIsNotNone(d.caso)
        self.assertRedirects(r, reverse("casos:detalle", args=[d.caso_id]))
        self.assertContains(c.post(reverse("casos:nuevo"), {**datos, "estudiante": self.estudiante.pk}),
                            "ya tiene un caso abierto de este tipo")

    def test_sesiones_hitos_y_cierre(self):
        caso = Caso.objects.create(estudiante=self.estudiante, tipo_proceso="seguimiento", responsable=self.psicologa,
                                   fecha_apertura=timezone.localdate() - datetime.timedelta(days=10))
        c = self.cliente(self.psicologa)
        # «Registrar sesión» del caso lleva a «Registrar atención» con el estudiante y el caso elegidos.
        url = reverse("casos:registrar_atencion") + "?estudiante=%d&caso=%d" % (self.estudiante.pk, caso.pk)
        self.assertRedirects(c.get(reverse("casos:sesion", args=[caso.pk])), url, fetch_redirect_response=False)
        datos = {"fecha": (timezone.localdate() - datetime.timedelta(days=20)).isoformat(), "hora": "10:00",
                 "duracion_minutos": 45, "tipo_atencion": "individual", "urgencia": "baja", "motivo": "conducta",
                 "nota": "Sesión de seguimiento inicial.", "accion": "registrar"}
        self.assertContains(c.post(url, datos), "anterior a la apertura")
        datos["fecha"] = timezone.localdate().isoformat()
        datos["hora"] = "00:00"
        c.post(url, datos)
        self.assertEqual(caso.sesiones.count(), 1)
        r = c.post(reverse("casos:hito", args=[caso.pk]), {"tipo": "hallazgo", "descripcion": "Hallazgo clínico",
                                                            "fecha": timezone.localdate().isoformat(),
                                                            "visible_profesor_jefe": "on"})
        self.assertContains(r, "no se comparten con el profesor jefe")
        r = c.post(reverse("casos:cerrar", args=[caso.pk]), {"fecha_cierre": timezone.localdate().isoformat(),
                                                             "confirmar": "on"})
        caso.refresh_from_db()
        self.assertEqual(caso.estado, "cerrado")
        self.assertEqual(caso.fecha_fin_retencion.year, timezone.localdate().year + 15)
        with self.assertRaises(ValidationError):
            SesionSeguimiento(caso=caso, profesional=self.psicologa, fecha_hora=timezone.now(),
                              nota="No debería guardarse").full_clean()

    def test_documento_cifrado_con_integridad(self):
        caso = Caso.objects.create(estudiante=self.estudiante, tipo_proceso="seguimiento", responsable=self.psicologa)
        c = self.cliente(self.psicologa)
        contenido = b"%PDF-1.7\nInforme externo de prueba"
        r = c.post(reverse("casos:documento", args=[caso.pk]),
                   {"tipo": "informe_externo", "archivo": SimpleUploadedFile("informe.pdf", contenido)})
        self.assertEqual(r.status_code, 302)
        doc = Documento.objects.get(caso=caso)
        guardado = almacenamiento._ruta(doc.ruta_objeto).read_bytes()
        self.assertNotIn(b"Informe externo", guardado)
        r = c.get(reverse("casos:descargar", args=[doc.pk]))
        self.assertEqual(r.content, contenido)
        self.assertContains(c.post(reverse("casos:documento", args=[caso.pk]),
                                   {"tipo": "otro", "archivo": SimpleUploadedFile("x.pdf", b"MZ ejecutable")}),
                            "no corresponde a un PDF")


class EvaluacionTest(PruebaBase):
    def setUp(self):
        self.caso = Caso.objects.create(estudiante=self.estudiante, tipo_proceso="pie_nee", responsable=self.pie,
                                        fecha_apertura=timezone.localdate() - datetime.timedelta(days=30))

    def datos(self):
        return {"tipo_evaluacion": "ingreso", "tipo_nee": "Trastorno específico del lenguaje",
                "fecha_evaluacion": timezone.localdate().isoformat(), "diagnostico": ""}

    def test_requiere_consentimiento_y_programa_reevaluacion(self):
        c = self.cliente(self.pie)
        r = c.post(reverse("evaluacion:nueva", args=[self.caso.pk]), self.datos())
        self.assertContains(r, "consentimiento vigente")
        self.consentir(self.estudiante, "evaluacion_pie")
        c.post(reverse("evaluacion:nueva", args=[self.caso.pk]), self.datos())
        ev = EvaluacionDiagnostica.objects.get(caso=self.caso)
        self.assertEqual(ev.fecha_reevaluacion.year, timezone.localdate().year + 2)   # NEE transitoria

    def test_no_se_cierra_sin_diagnostico_ni_participantes(self):
        ev = EvaluacionDiagnostica.objects.create(caso=self.caso, tipo_nee="TEL", fecha_evaluacion=timezone.localdate())
        c = self.cliente(self.pie)
        c.post(reverse("evaluacion:cerrar", args=[ev.pk]))
        ev.refresh_from_db()
        self.assertEqual(ev.estado, "en_proceso")
        ev.diagnostico = "Diagnóstico integral"
        ev.save()
        ParticipacionEvaluacion.objects.create(evaluacion=ev, usuario=self.pie, rol_profesional="Coordinadora",
                                               aporte="Pruebas pedagógicas")
        c.post(reverse("evaluacion:cerrar", args=[ev.pk]))
        ev.refresh_from_db()
        self.assertEqual(ev.estado, "cerrada")

    def test_evaluacion_no_aplica_a_seguimiento(self):
        caso = Caso.objects.create(estudiante=self.estudiante2, tipo_proceso="seguimiento", responsable=self.psicologa)
        with self.assertRaises(ValidationError):
            EvaluacionDiagnostica(caso=caso, tipo_nee="x", fecha_evaluacion=timezone.localdate()).full_clean()

    def test_un_plan_vigente_por_tipo(self):
        PlanApoyo.objects.create(estudiante=self.estudiante, tipo="paci", adecuaciones="Adecuaciones existentes del plan.",
                                 fecha_inicio=timezone.localdate())
        c = self.cliente(self.pie)
        r = c.post(reverse("evaluacion:plan_nuevo", args=[self.estudiante.pk]),
                   {"tipo": "paci", "fecha_inicio": timezone.localdate().isoformat(),
                    "adecuaciones": "Más tiempo en evaluaciones escritas."})
        self.assertContains(r, "ya tiene un plan vigente de este tipo")

    def test_plan_cerrado_no_se_edita_y_profesor_no_gestiona(self):
        plan = PlanApoyo.objects.create(estudiante=self.estudiante, tipo="paci", fecha_inicio=timezone.localdate(),
                                        adecuaciones="Adecuaciones existentes del plan.")
        self.assertEqual(self.cliente(self.profesor).get(reverse("evaluacion:plan_editar", args=[plan.pk])).status_code, 403)
        c = self.cliente(self.pie)
        c.post(reverse("evaluacion:plan_cerrar", args=[plan.pk]), {"fecha_termino": timezone.localdate().isoformat()})
        plan.refresh_from_db()
        self.assertEqual(plan.estado, "cerrado")
        r = c.post(reverse("evaluacion:plan_editar", args=[plan.pk]),
                   {"tipo": "paci", "fecha_inicio": timezone.localdate().isoformat(), "adecuaciones": "Cambio posterior al cierre."})
        self.assertRedirects(r, reverse("estudiantes:detalle", args=[self.estudiante.pk]), fetch_redirect_response=False)
        plan.refresh_from_db()
        self.assertEqual(plan.adecuaciones, "Adecuaciones existentes del plan.")

    def test_aviso_de_reevaluacion(self):
        ev = EvaluacionDiagnostica.objects.create(caso=self.caso, tipo_nee="TEL", diagnostico="Dx",
                                                  fecha_evaluacion=timezone.localdate() - datetime.timedelta(days=700),
                                                  estado="cerrada")
        ev.fecha_reevaluacion = timezone.localdate() + datetime.timedelta(days=30)
        ev.save()
        self.assertEqual(procesar_reevaluaciones(), 1)
        self.assertEqual(procesar_reevaluaciones(), 0)      # no duplica avisos
        self.assertEqual(AvisoReevaluacion.objects.get().destinatario, self.pie)

    def test_informe_no_se_valida_con_marcas_pendientes(self):
        informe = Informe.objects.create(caso=self.caso, tipo="familia",
                                         contenido="Texto del informe. [VERIFICAR] completar conclusiones.")
        c = self.cliente(self.pie)
        c.post(reverse("evaluacion:informe_validar", args=[informe.pk]))
        informe.refresh_from_db()
        self.assertEqual(informe.estado, "borrador")
        r = c.post(reverse("evaluacion:informe_entregar", args=[informe.pk]))
        self.assertEqual(r.status_code, 302)
        informe.refresh_from_db()
        self.assertIsNone(informe.fecha_entrega)


class PreliminarFudeiTest(PruebaBase):
    """RF-06: la versión preliminar del FUDEI parte de los datos ya registrados y no se valida con marcas pendientes."""

    def setUp(self):
        self.caso = Caso.objects.create(estudiante=self.estudiante, tipo_proceso="pie_nee", responsable=self.pie,
                                        fecha_apertura=timezone.localdate() - datetime.timedelta(days=30))

    def test_borrador_con_datos_registrados(self):
        ev = EvaluacionDiagnostica.objects.create(caso=self.caso, tipo_nee="Trastorno específico del lenguaje",
                                                  fecha_evaluacion=timezone.localdate())
        ParticipacionEvaluacion.objects.create(evaluacion=ev, usuario=self.pie, rol_profesional="Coordinadora PIE",
                                               aporte="Aplicó pruebas pedagógicas.")
        PlanApoyo.objects.create(estudiante=self.estudiante, tipo="paci", fecha_inicio=timezone.localdate(),
                                 adecuaciones="Instrucciones breves y apoyo visual en clases.")
        c = self.cliente(self.pie)
        r = c.get(reverse("evaluacion:informe_nuevo", args=[self.caso.pk]), {"tipo": "preliminar_fudei"})
        texto = r.context["form"].initial["contenido"]
        for esperado in ("VERSIÓN PRELIMINAR DEL FUDEI", "Martina", "Trastorno específico del lenguaje",
                         "Coordinadora PIE", "Aplicó pruebas pedagógicas.", "PACI", "apoyo visual",
                         "[PENDIENTE: síntesis del diagnóstico integral]"):
            self.assertIn(esperado, texto)
        c.post(reverse("evaluacion:informe_nuevo", args=[self.caso.pk]), {"tipo": "preliminar_fudei", "contenido": texto})
        informe = Informe.objects.get(caso=self.caso)
        c.post(reverse("evaluacion:informe_validar", args=[informe.pk]))
        informe.refresh_from_db()
        self.assertEqual(informe.estado, "borrador")        # quedan marcas [PENDIENTE]: no se valida

    def test_modo_privado_desactiva_al_preparar(self):
        c = self.cliente(self.pie)
        c.post(reverse("cuentas:privacidad_ocultar"))
        r = c.get(reverse("evaluacion:informe_nuevo", args=[self.caso.pk]), {"tipo": "preliminar_fudei"})
        self.assertContains(r, "Modo privado desactivado")
