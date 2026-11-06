"""Pantallas «Estudiantes» del prototipo v1: lista, registro con apoderado, Excel, PDF, retiro, cursos, promoción y egresados."""
import datetime
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.auditoria.models import EventoAuditoria
from apps.casos.models import Caso
from apps.core.documentos import libro_excel
from apps.estudiantes import servicios
from apps.estudiantes.forms import COLUMNAS_IMPORTACION
from apps.estudiantes.models import Curso, Estudiante, ProcesoPromocion

from .base import PruebaBase, rut


def _xlsx(filas):
    return SimpleUploadedFile("estudiantes.xlsx", libro_excel([("Estudiantes", [r for _, r in COLUMNAS_IMPORTACION], filas)]))


class ListaTest(PruebaBase):
    def test_indicadores_pestanas_y_busqueda(self):
        otro = self.nuevo_estudiante(24_700_111, "Luis Andrés", "Mora Ruiz", self.curso)
        otro.fecha_egreso, otro.tipo_salida = self.hoy - datetime.timedelta(days=3), "retiro"
        otro.save()
        c = self.cliente(self.psicologa)
        r = c.get(reverse("estudiantes:lista"))
        self.assertEqual((r.context["kpi"]["total"], r.context["kpi"]["activos"], r.context["kpi"]["inactivos"]), (3, 2, 1))
        self.assertContains(r, "Tasa de retiro")
        r = c.get(reverse("estudiantes:lista") + "?estado=inactivos")
        self.assertEqual([e.pk for e in r.context["pagina"]], [otro.pk])
        # Buscador global: una sola coincidencia lleva directo a la ficha; busca todas las palabras.
        r = c.get(reverse("estudiantes:lista"), {"q": "martina pérez", "ir": "1"})
        self.assertRedirects(r, reverse("estudiantes:detalle", args=[self.estudiante.pk]))
        r = c.get(reverse("estudiantes:lista"), {"q": "Martina Contreras"})
        self.assertEqual(len(r.context["pagina"]), 0)

    def test_profesor_jefe_solo_ve_su_curso(self):
        r = self.cliente(self.profesor).get(reverse("estudiantes:lista"))
        self.assertEqual([e.pk for e in r.context["pagina"]], [self.estudiante.pk])
        self.assertNotContains(r, "Importar Excel")
        self.assertEqual(self.cliente(self.profesor).get(reverse("estudiantes:exportar")).status_code, 403)


class RegistroTest(PruebaBase):
    def datos(self, **extra):
        return {"rut": "12.345.678-5", "primer_nombre": "Ana", "segundo_nombre": "María", "apellido_paterno": "Gómez",
                "apellido_materno": "Paz", "nombre_social": "", "fecha_nacimiento": "2016-04-10", "curso": self.curso.pk,
                "necesidad_educativa": "ninguna", "apo-parentesco": "madre", **extra}

    def test_registro_con_apoderado_opcional(self):
        c = self.cliente(self.psicologa)
        r = c.post(reverse("estudiantes:crear"), self.datos(**{"apo-telefono": "912345678"}))
        self.assertContains(r, "al menos un nombre y un apellido")      # si se llena el apoderado, se valida completo
        r = c.post(reverse("estudiantes:crear"), self.datos(**{"apo-nombre_completo": "Rosa Paz", "apo-telefono": "912345678"}))
        e = Estudiante.objects.get(rut="12345678-5")
        self.assertRedirects(r, reverse("estudiantes:detalle", args=[e.pk]))
        self.assertEqual((e.nombres, e.apellidos), ("Ana María", "Gómez Paz"))
        self.assertEqual(e.apoderado_titular().telefono, "+56912345678")

    def test_nombre_con_caracteres_invalidos(self):
        r = self.cliente(self.psicologa).post(reverse("estudiantes:crear"), self.datos(primer_nombre="Ana3"))
        self.assertContains(r, "Use solo letras")


class ExcelPdfTest(PruebaBase):
    def test_importacion_valida_todo_antes_de_guardar(self):
        c = self.cliente(self.admin)
        plantilla = c.get(reverse("estudiantes:plantilla"))
        self.assertEqual(plantilla["Content-Type"].split(";")[0],
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        buena = [rut(21_111_111), "Pedro", "", "Soto", "Lagos", "", "10-03-2015", "5° Básico A", "", "No", "", "Sí",
                 "Carla Soto", "+56 9 8765 4321", ""]
        mala = [rut(21_222_222), "Juan", "", "Díaz", "Mena", "", "10-03-2015", "9° Básico Z", "", "Sí", "", "No", "", "", ""]
        r = c.post(reverse("estudiantes:importar"), {"archivo": _xlsx([buena, mala])})
        self.assertContains(r, "Filas con errores")
        self.assertContains(r, "no existe")
        self.assertFalse(Estudiante.objects.filter(primer_nombre="Pedro").exists())     # nada se importa si hay errores
        r = c.post(reverse("estudiantes:importar"), {"archivo": _xlsx([buena])})
        self.assertRedirects(r, reverse("estudiantes:lista"))
        pedro = Estudiante.objects.get(primer_nombre="Pedro")
        self.assertTrue(pedro.prioritario)
        self.assertEqual(pedro.apoderado_titular().nombre_completo, "Carla Soto")

    def test_importacion_rechaza_archivos_que_no_son_excel(self):
        r = self.cliente(self.admin).post(reverse("estudiantes:importar"),
                                          {"archivo": SimpleUploadedFile("x.xlsx", b"MZ no es un zip")})
        self.assertContains(r, "no corresponde a un Excel válido")

    def test_exportacion_auditada_y_sin_formulas(self):
        self.estudiante.nombre_social = "=HYPERLINK(\"http://x\")"
        self.estudiante.save()
        r = self.cliente(self.psicologa).get(reverse("estudiantes:exportar"))
        from openpyxl import load_workbook
        hoja = load_workbook(io.BytesIO(r.content)).active
        celdas = [c for fila in hoja.iter_rows() for c in fila if c.value == self.estudiante.nombre_social]
        self.assertEqual(celdas[0].data_type, "s")                 # se guarda como texto, nunca como fórmula
        self.assertTrue(EventoAuditoria.objects.filter(accion="exportacion", entidad="estudiante").exists())

    def test_ficha_y_nominas_en_pdf(self):
        c = self.cliente(self.psicologa)
        r = c.get(reverse("estudiantes:ficha_pdf", args=[self.estudiante.pk]))
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF"))
        r = c.get(reverse("estudiantes:cursos_pdf") + "?ids=%d&ids=%d" % (self.curso.pk, self.otro_curso.pk))
        self.assertTrue(r.content.startswith(b"%PDF"))
        self.assertEqual(self.cliente(self.profesor).get(reverse("estudiantes:ficha_pdf", args=[self.estudiante2.pk]))
                         .status_code, 403)


class RetiroTest(PruebaBase):
    def test_no_se_retira_con_casos_abiertos(self):
        c = self.cliente(self.psicologa)
        Caso.objects.create(estudiante=self.estudiante, tipo_proceso="seguimiento", responsable=self.psicologa)
        url = reverse("estudiantes:inactivar", args=[self.estudiante.pk])
        r = c.post(url, {"fecha_retiro": self.hoy.isoformat(), "confirmar": "on"})
        self.assertContains(r, "casos abiertos")
        r = c.post(reverse("estudiantes:inactivar", args=[self.estudiante2.pk]),
                   {"fecha_retiro": self.hoy.isoformat(), "confirmar": "on"})
        self.estudiante2.refresh_from_db()
        self.assertEqual((self.estudiante2.estado, self.estudiante2.tipo_salida), ("inactivo", "retiro"))
        c.post(reverse("estudiantes:reactivar", args=[self.estudiante2.pk]))
        self.estudiante2.refresh_from_db()
        self.assertTrue(self.estudiante2.activo)


class CursosPromocionTest(PruebaBase):
    def test_cursos_agrupados(self):
        r = self.cliente(self.psicologa).get(reverse("estudiantes:cursos"))
        self.assertEqual([g["nombre"] for g in r.context["grupos"]], ["Básica"])
        self.assertNotContains(r, "Crear curso")                    # solo el administrador crea cursos
        self.assertContains(self.cliente(self.admin).get(reverse("estudiantes:cursos")), "Crear curso")

    def test_promocion_en_tres_pasos(self):
        anio = self.hoy.year - 1                                    # año ya terminado: se puede procesar
        cuarto = Curso.objects.create(sede=self.sedes["Central"], nivel="4M", letra="A", anio_escolar=anio)
        quinto = Curso.objects.create(sede=self.sedes["Central"], nivel="5B", letra="A", anio_escolar=anio)
        egresa = self.nuevo_estudiante(20_300_300, "Laura", "Pino Soto", cuarto)
        repite = self.nuevo_estudiante(24_300_301, "Mario", "Lagos Paz", quinto)
        pasa = self.nuevo_estudiante(24_300_302, "Nora", "Vera Ríos", quinto)
        c = self.cliente(self.admin)
        base = "?anio=%d" % anio
        r = c.post(reverse("estudiantes:promocion") + base, {"terminales": [], "accion": "continuar"}, follow=True)
        self.assertContains(r, "no tiene un nivel siguiente")        # 4° Medio debe ser terminal
        r = c.post(reverse("estudiantes:promocion") + base, {"terminales": [cuarto.pk], "accion": "continuar"})
        self.assertRedirects(r, reverse("estudiantes:promocion_revisar") + base, fetch_redirect_response=False)
        c.post(reverse("estudiantes:promocion_revisar") + base, {"repite": [repite.pk], "accion": "continuar"})
        r = c.post(reverse("estudiantes:promocion_procesar") + base)
        proceso = ProcesoPromocion.objects.get(anio=anio)
        self.assertEqual(proceso.estado, "procesado")
        for e in (egresa, repite, pasa):
            e.refresh_from_db()
        self.assertEqual((egresa.estado, egresa.tipo_salida), ("egresado", "egreso"))
        self.assertEqual((repite.curso.nivel, repite.curso.anio_escolar), ("5B", anio + 1))
        self.assertEqual((pasa.curso.nivel, pasa.curso.anio_escolar), ("6B", anio + 1))
        r = c.get(reverse("estudiantes:egresados"))
        self.assertContains(r, "Pino Soto")
        self.assertContains(c.post(reverse("estudiantes:promocion_procesar") + base, follow=True), "ya fue procesado")

    def test_el_fin_de_anio_en_curso_no_se_procesa_antes_de_noviembre(self):
        proceso = servicios.proceso_del_anio(self.hoy.year)
        self.assertEqual(servicios.puede_procesar(proceso, datetime.date(self.hoy.year, 10, 31)), False)
        self.assertEqual(servicios.puede_procesar(proceso, datetime.date(self.hoy.year, 11, 1)), True)

    def test_promocion_solo_administrador(self):
        self.assertEqual(self.cliente(self.psicologa).get(reverse("estudiantes:promocion")).status_code, 403)
        self.assertEqual(self.cliente(self.admin).get(reverse("estudiantes:promocion")).status_code, 200)
        self.assertEqual(timezone.localdate().year, self.hoy.year)
