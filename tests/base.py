"""Utilidades comunes de las pruebas: datos mínimos ficticios y clientes autenticados con segundo factor."""
import datetime
import shutil
import tempfile

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from apps.core.inicializacion import inicializar_sistema
from apps.core.models import Sede
from apps.core.validadores import calcular_dv
from apps.cuentas.models import Rol, Usuario, UsuarioRol
from apps.cumplimiento.models import Consentimiento
from apps.estudiantes.models import Apoderado, Curso, Estudiante, EstudianteApoderado

CLAVE = "ClaveSegura2026"
_TMP = tempfile.mkdtemp(prefix="bienestar_pruebas_")


def rut(numero):
    return "%d-%s" % (numero, calcular_dv(numero))


@override_settings(SECURE_SSL_REDIRECT=False, ADJUNTOS_DIR=__import__("pathlib").Path(_TMP) / "adjuntos",
                   BITACORA_EXPORT_DIR=__import__("pathlib").Path(_TMP) / "bitacora",
                   EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "pruebas"}})
class PruebaBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        inicializar_sistema()
        cls.sedes = {s.nombre: s for s in Sede.objects.all()}
        cls.hoy = timezone.localdate()
        cls.psicologa = cls.usuario("psi@demo.cl", "Paula Soto Ruiz", "psicologa", "psicologa_denunciante")
        cls.psicologa2 = cls.usuario("psi2@demo.cl", "Carla Díaz Lara", "psicologa")
        cls.social = cls.usuario("social@demo.cl", "Sofía Mena Paz", "asistente_social", "encargada_convivencia")
        cls.pie = cls.usuario("pie@demo.cl", "Marta Leal Cruz", "coordinacion_pie")
        cls.profesor = cls.usuario("profe@demo.cl", "Pedro Ruiz Vega", "profesor_jefe")
        cls.inspectora = cls.usuario("insp@demo.cl", "Inés Parra Toro", ("inspectoria", "Básica"))
        cls.directora = cls.usuario("dir@demo.cl", "Diana Rivas Soto", "directora")
        cls.admin = cls.usuario("admin@demo.cl", "Andrés Olea Ríos", "administrador")
        cls.curso = Curso.objects.create(sede=cls.sedes["Central"], nivel="5B", letra="A", anio_escolar=cls.hoy.year,
                                         profesor_jefe=cls.profesor)
        cls.otro_curso = Curso.objects.create(sede=cls.sedes["Básica"], nivel="2B", letra="B", anio_escolar=cls.hoy.year)
        cls.estudiante = cls.nuevo_estudiante(24_512_331, "Martina", "Pérez Lagos", cls.curso, "transitoria", True)
        cls.estudiante2 = cls.nuevo_estudiante(25_904_118, "Emilia", "Contreras Ávila", cls.otro_curso)
        cls.apoderado = cls.estudiante.apoderado_titular()

    @classmethod
    def usuario(cls, correo, nombre, *roles):
        u = Usuario.objects.create_user(correo, nombre, CLAVE)
        for r in roles:
            codigo, sede = (r, None) if isinstance(r, str) else (r[0], Sede.objects.get(nombre=r[1]))
            UsuarioRol.objects.create(usuario=u, rol=Rol.objects.get(codigo=codigo), sede=sede,
                                      vigente_desde=timezone.localdate() - datetime.timedelta(days=30))
        return u

    @classmethod
    def nuevo_estudiante(cls, numero, nombres, apellidos, curso, nee="ninguna", pie=False):
        """`nombres` y `apellidos` como texto («María José», «Pérez Lagos»): se separan en los campos del modelo."""
        n, a = nombres.split(" ", 1) + [""], apellidos.split(" ", 1) + [""]
        e = Estudiante.objects.create(rut=rut(numero), primer_nombre=n[0], segundo_nombre=n[1], apellido_paterno=a[0],
                                      apellido_materno=a[1] or "Demo",
                                      fecha_nacimiento=datetime.date(timezone.localdate().year - 10, 5, 5), curso=curso,
                                      necesidad_educativa=nee, en_pie=pie)
        a = Apoderado.objects.create(rut=rut(numero - 12_000_000), nombre_completo="Rosa %s" % apellidos,
                                     telefono="+56991234567", correo="%s@correo.cl" % nombres.lower())
        EstudianteApoderado.objects.create(estudiante=e, apoderado=a, parentesco="madre", es_titular=True)
        return e

    def consentir(self, estudiante, *alcances):
        for alcance in alcances:
            Consentimiento.objects.create(estudiante=estudiante, apoderado=estudiante.apoderado_titular(), alcance=alcance,
                                          fecha_otorgamiento=self.hoy - datetime.timedelta(days=10))

    def cliente(self, usuario, mfa=True):
        c = Client()
        c.force_login(usuario)
        if mfa:
            s = c.session
            s["mfa_ok"] = True
            s.save()
        return c

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_TMP, ignore_errors=True)
