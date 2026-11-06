"""Carga datos de DEMOSTRACIÓN ficticios para probar la plataforma. Ninguna persona ni situación es real.

Uso: python manage.py cargar_datos_demo

Crea los 14 cursos del año (Prekínder a 4° Medio), unos 60 estudiantes con RUT válidos pero inventados, casos y
atenciones, alertas, anotaciones, conflictos, situación conductual, protocolos, el plan de gestión y un proceso de
promoción del año anterior con sus egresados.
"""
import datetime
import random

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.alertas.models import AlertaRiesgo, GestionAlerta
from apps.alertas.servicios import notificar_alerta
from apps.casos.models import Caso, Derivacion, Hito, SesionSeguimiento
from apps.convivencia.models import ActividadPlan, Anotacion, Conflicto, ProtocoloActivado, RegistroConductual
from apps.convivencia.servicios import activar_desde_alerta
from apps.core.inicializacion import inicializar_sistema
from apps.core.models import Sede
from apps.core.validadores import calcular_dv, sumar_anios
from apps.cuentas.models import Rol, Usuario, UsuarioRol
from apps.cumplimiento.models import Consentimiento
from apps.cumplimiento.servicios import proponer_retenciones
from apps.estudiantes.models import (NIVELES, Apoderado, Curso, Estudiante, EstudianteApoderado, ProcesoPromocion,
                                     PromocionEstudiante)
from apps.evaluacion.models import EvaluacionDiagnostica, ParticipacionEvaluacion, PlanApoyo
from apps.evaluacion.servicios import procesar_reevaluaciones

CLAVE_DEMO = "Bienestar2026"

USUARIOS = [  # (correo, nombre, roles, especialidad, teléfono)
    ("camila.fuentes@demo.cl", "Camila Fuentes Araya", ["psicologa", "psicologa_denunciante"], "Psicóloga", "+56991110001"),
    ("javiera.morales@demo.cl", "Javiera Morales Pinto", ["psicologa"], "Psicóloga", ""),
    ("daniela.vergara@demo.cl", "Daniela Vergara Soto", ["asistente_social", "encargada_convivencia"],
     "Trabajadora social · Encargada de Convivencia", "+56991110003"),
    ("marcela.tapia@demo.cl", "Marcela Tapia Rivas", ["coordinacion_pie"], "Educadora diferencial", ""),
    ("rodrigo.castro@demo.cl", "Rodrigo Castro Muñoz", ["profesor_jefe"], "Profesor de Lenguaje", ""),
    ("patricia.lagos@demo.cl", "Patricia Lagos Vidal", [("inspectoria", "Básica")], "Inspectora", ""),
    ("ximena.herrera@demo.cl", "Ximena Herrera Díaz", ["directora"], "Directora", ""),
    ("tomas.reyes@demo.cl", "Tomás Reyes Olivares", ["administrador"], "Administración", ""),
]

# Cursos del año: (nivel, sede)
CURSOS = [("PK", "Prebásica"), ("K", "Prebásica")] + [("%dB" % i, "Básica") for i in range(1, 7)] + \
         [("7B", "Central"), ("8B", "Central")] + [("%dM" % i, "Central") for i in range(1, 5)]

# Estudiantes con historia en la demostración: (RUT, nombres, apellidos, curso, NEE, PIE, condicional, prioritario)
PROTAGONISTAS = [
    (24_512_331, ("Martina", ""), ("Pérez", "Lagos"), "5B", "ninguna", False, False, False),
    (24_618_902, ("Benjamín", "Andrés"), ("Soto", "Carrasco"), "5B", "transitoria", True, False, True),
    (24_733_415, ("Florencia", ""), ("Muñoz", "Reyes"), "5B", "ninguna", False, True, False),
    (24_801_227, ("Agustín", ""), ("Rojas", "Villalobos"), "5B", "permanente", True, False, False),
    (25_904_118, ("Emilia", "Paz"), ("Contreras", "Ávila"), "2B", "transitoria", True, False, False),
    (25_977_640, ("Tomás", ""), ("Navarro", "Fuentes"), "2B", "ninguna", False, False, True),
    (21_345_118, ("Vicente", ""), ("Araya", "Molina"), "2M", "ninguna", False, False, False),
    (21_402_993, ("Antonia", "Belén"), ("Sepúlveda", "Castro"), "8B", "ninguna", False, False, True),
]
NOMBRES = ["Sofía", "Mateo", "Isidora", "Lucas", "Josefa", "Maximiliano", "Trinidad", "Joaquín", "Amanda", "Gaspar",
           "Catalina", "Clemente", "Renata", "Julián", "Maite", "Bastián", "Agustina", "Alonso", "Fernanda", "Cristóbal",
           "Javiera", "Facundo", "Valentina", "Santiago", "Rafaela", "Diego", "Emma", "León", "Colomba", "Ignacio"]
APELLIDOS = ["González", "Muñoz", "Rojas", "Díaz", "Pérez", "Soto", "Contreras", "Silva", "Martínez", "Sepúlveda",
             "Morales", "Rodríguez", "López", "Fuentes", "Hernández", "Torres", "Araya", "Flores", "Espinoza",
             "Valenzuela", "Castillo", "Tapia", "Reyes", "Gutiérrez", "Castro", "Pizarro", "Álvarez", "Vásquez",
             "Sánchez", "Fernández"]
EDAD_POR_NIVEL = {codigo: 4 + i for i, (codigo, _) in enumerate(NIVELES)}

ACTIVIDADES_PLAN = [  # (días atrás, título, medio de verificación) — actividades del prototipo v1
    (23, "PIE 5° y 6° – Taller de habilidades", "Planificación"),
    (27, "PIE 1° y 2° Medio – Taller de orientación vocacional", "PPT y actividades"),
    (27, "PIE 7° y 8° – Taller de habilidades", "Planificación"),
    (30, "PIE 5° y 6° – Taller de habilidades ejecutivas", "Planificación"),
    (34, "Sexualidad y afectividad: cómo enfrentar la preadolescencia y adolescencia",
     "PPT y planificación de clase en coordinación ADIE"),
]

DESCRIPCIONES_ANOTACION = {
    "positiva": ["Colabora activamente con sus compañeros en el trabajo grupal.", "Destaca por su responsabilidad con las tareas.",
                 "Ayuda a un compañero que lo necesitaba durante el recreo.", "Participa con entusiasmo en la actividad de la clase."],
    "moderada": ["Interrumpe reiteradamente la clase pese a los llamados de atención.", "No trae los materiales solicitados.",
                 "Usa el celular durante la clase sin autorización."],
    "grave": ["Se retira de la sala sin autorización del profesor.", "Responde de manera irrespetuosa a un docente."],
    "gravisima": ["Agrede físicamente a un compañero durante el recreo."],
}


class Command(BaseCommand):
    help = "Carga datos ficticios de demostración (usuarios, cursos, estudiantes, casos, convivencia y alertas)."

    def add_arguments(self, parser):
        parser.add_argument("--reiniciar", action="store_true", help="(Informativo) explica cómo volver a cargarlos.")

    def handle(self, *args, **o):
        with transaction.atomic():
            resumen = self._cargar(o)
        # El resumen se imprime después de confirmar la transacción (y de los avisos por correo que se envían al confirmar).
        self.stdout.write(self.style.SUCCESS(resumen))
        for correo, nombre, lista_roles, *_ in USUARIOS:
            self.stdout.write("  %-28s %s" % (correo, ", ".join(r if isinstance(r, str) else r[0] for r in lista_roles)))

    # ------------------------------------------------------------------------------------------------------ carga
    def _cargar(self, o):
        inicializar_sistema()
        if Usuario.objects.filter(correo__endswith="@demo.cl").exists():
            raise CommandError("Ya hay datos de demostración. Para volver a cargarlos, borre la base de datos (o el archivo "
                               "db.sqlite3) y vuelva a migrar: la bitácora es de solo inserción y no admite borrar eventos.")
        self.rnd = random.Random(2026)
        self.hoy = hoy = timezone.localdate()
        self.ahora = timezone.now()
        self.anio = anio = hoy.year
        # Inicio del año escolar (marzo) o, si la demo se carga en verano, los últimos cuatro meses.
        self.inicio_anio = datetime.date(anio, 3, 1) if hoy > datetime.date(anio, 3, 20) else hoy - datetime.timedelta(days=120)
        sedes = {s.nombre: s for s in Sede.objects.all()}
        roles = {r.codigo: r for r in Rol.objects.all()}

        u = {}
        for correo, nombre, lista_roles, especialidad, telefono in USUARIOS:
            usuario = Usuario.objects.create_user(correo, nombre, CLAVE_DEMO, especialidad=especialidad, telefono=telefono)
            usuario.fecha_alta = self.ahora - datetime.timedelta(days=210)
            usuario.save(update_fields=["fecha_alta"])
            for r in lista_roles:
                codigo, sede = (r, None) if isinstance(r, str) else (r[0], sedes[r[1]])
                UsuarioRol.objects.create(usuario=usuario, rol=roles[codigo], sede=sede,
                                          vigente_desde=hoy - datetime.timedelta(days=400))
            u[correo.split(".")[0]] = usuario
        self.u = u

        cursos = {nivel: Curso.objects.create(sede=sedes[sede], nivel=nivel, letra="A", anio_escolar=anio,
                                              profesor_jefe=u["rodrigo"] if nivel == "5B" else None)
                  for nivel, sede in CURSOS}
        self.cursos = cursos
        est = self._estudiantes(cursos)
        self._egresados_y_promocion(sedes, cursos)
        self._casos_y_atenciones(est)
        self._alertas(est, sedes)
        self._convivencia(cursos)
        self._plan()

        # Egresado hace 16 años: debe aparecer en la propuesta de retención (RNF-10)
        antiguo = Estudiante.objects.create(
            rut="%d-%s" % (19_876_543, calcular_dv(19_876_543)), primer_nombre="Ignacio", apellido_paterno="Valdés",
            apellido_materno="Ortiz", fecha_nacimiento=datetime.date(hoy.year - 30, 5, 5),
            curso=Curso.objects.create(sede=sedes["Central"], nivel="4M", letra="A", anio_escolar=anio - 16),
            fecha_egreso=sumar_anios(hoy, -16), tipo_salida="egreso")
        Caso.objects.create(estudiante=antiguo, tipo_proceso="seguimiento", responsable=u["camila"], estado="cerrado",
                            fecha_apertura=sumar_anios(hoy, -17), fecha_cierre=sumar_anios(hoy, -16) - datetime.timedelta(days=30))

        avisos = procesar_reevaluaciones()
        retenciones = proponer_retenciones()
        return ("Datos de demostración cargados: %d usuarios, %d cursos, %d estudiantes, %d atenciones, %d anotaciones, "
                "%d conflictos, %d avisos de reevaluación y %d propuesta(s) de retención.\n"
                "Clave de todos los usuarios de demostración: %s"
                % (len(USUARIOS), Curso.objects.count(), Estudiante.objects.count(), SesionSeguimiento.objects.count(),
                   Anotacion.objects.count(), Conflicto.objects.count(), avisos, retenciones, CLAVE_DEMO))

    def _fecha_en_anio(self, desde_dias=None):
        """Fecha al azar entre el inicio del año escolar y hoy."""
        total = max((self.hoy - self.inicio_anio).days, 1)
        return self.inicio_anio + datetime.timedelta(days=self.rnd.randint(0, total))

    # ------------------------------------------------------------------------------------------------------ estudiantes
    def _nuevo_estudiante(self, numero, nombres, apellidos, curso, nee="ninguna", pie=False, condicional=False,
                          prioritario=False, nombre_social="", i=0):
        edad = EDAD_POR_NIVEL[curso.nivel]
        e = Estudiante.objects.create(
            rut="%d-%s" % (numero, calcular_dv(numero)), primer_nombre=nombres[0], segundo_nombre=nombres[1],
            apellido_paterno=apellidos[0], apellido_materno=apellidos[1], nombre_social=nombre_social,
            fecha_nacimiento=datetime.date(self.anio - edad - 1, 1 + i % 12, 1 + (i * 7) % 27), curso=curso,
            fecha_ingreso=datetime.date(self.anio - self.rnd.randint(0, min(edad - 3, 6)), 3, 1),
            necesidad_educativa=nee, en_pie=pie, matricula_condicional=condicional, prioritario=prioritario)
        numero_apo = 12_345_600 + i * 7_331
        nombre_apo = "%s %s" % (self.rnd.choice(["Carolina", "Paola", "Marcela", "Andrea", "Claudia", "Jorge", "Luis",
                                                 "Patricio", "Verónica", "Pamela"]), apellidos[0])
        a = Apoderado.objects.create(rut="%d-%s" % (numero_apo, calcular_dv(numero_apo)), nombre_completo=nombre_apo,
                                     telefono="+5699%07d" % (1234560 + i), correo="apoderado%d@correo-demo.cl" % (i + 1))
        EstudianteApoderado.objects.create(estudiante=e, apoderado=a, parentesco=self.rnd.choice(["madre", "padre"]),
                                           es_titular=True)
        return e

    def _estudiantes(self, cursos):
        est, i = {}, 0
        for numero, nombres, apellidos, nivel, nee, pie, cond, prio in PROTAGONISTAS:
            est[nombres[0]] = self._nuevo_estudiante(numero, nombres, apellidos, cursos[nivel], nee, pie, cond, prio, i=i)
            i += 1
        # Relleno: entre 3 y 5 estudiantes por curso, con nombres y RUT inventados.
        for nivel, _ in CURSOS:
            for _ in range(self.rnd.randint(3, 5)):
                numero = 22_000_000 + i * 104_729 % 3_000_000 + i
                nombres = (self.rnd.choice(NOMBRES), self.rnd.choice(["", "", self.rnd.choice(NOMBRES)]))
                apellidos = (self.rnd.choice(APELLIDOS), self.rnd.choice(APELLIDOS))
                pie = self.rnd.random() < 0.15
                self._nuevo_estudiante(numero, nombres, apellidos, cursos[nivel], nee="transitoria" if pie else "ninguna",
                                       pie=pie, prioritario=self.rnd.random() < 0.2, i=i)
                i += 1
        # Nombre social (Circular 812) y dos retiros del año.
        otro = Estudiante.objects.filter(curso=cursos["PK"]).order_by("pk")[1]
        otro.nombre_social = "Alex"
        otro.save(update_fields=["nombre_social"])
        for nivel in ("1B", "6B"):
            retirado = Estudiante.objects.filter(curso=cursos[nivel]).order_by("-pk").first()
            retirado.fecha_egreso, retirado.tipo_salida = self.hoy - datetime.timedelta(days=40), "retiro"
            retirado.save(update_fields=["fecha_egreso", "tipo_salida"])

        for nombre in ("Martina", "Benjamín", "Agustín", "Emilia"):
            e = est[nombre]
            titular = e.apoderado_titular()
            for alcance in ("seguimiento", "uso_ia") + (("evaluacion_pie",) if e.en_pie else ()):
                Consentimiento.objects.create(estudiante=e, apoderado=titular, alcance=alcance,
                                              fecha_otorgamiento=self.hoy - datetime.timedelta(days=200))
        return est

    def _egresados_y_promocion(self, sedes, cursos):
        """Proceso de promoción del año anterior ya procesado: tres egresados de 4° Medio y un repitente de 3° Básico."""
        previo = self.anio - 1
        cuarto = Curso.objects.create(sede=sedes["Central"], nivel="4M", letra="A", anio_escolar=previo)
        tercero = Curso.objects.create(sede=sedes["Básica"], nivel="3B", letra="A", anio_escolar=previo)
        proceso = ProcesoPromocion.objects.create(anio=previo, estado="procesado", procesado_por=self.u["tomas"],
                                                  fecha_proceso=timezone.make_aware(datetime.datetime(previo, 12, 15, 10)))
        proceso.cursos_terminales.set([cuarto])
        for j, (nombres, apellidos) in enumerate([(("Constanza", ""), ("Lagos", "Pino")), (("Nicolás", "Esteban"), ("Bravo", "Díaz")),
                                                  (("Francisca", ""), ("Olivares", "Rey"))]):
            numero = 20_100_000 + j * 11_117
            e = Estudiante.objects.create(
                rut="%d-%s" % (numero, calcular_dv(numero)), primer_nombre=nombres[0], segundo_nombre=nombres[1],
                apellido_paterno=apellidos[0], apellido_materno=apellidos[1],
                fecha_nacimiento=datetime.date(previo - 18, 2 + j, 10), curso=cuarto,
                fecha_ingreso=datetime.date(previo - 12, 3, 1), fecha_egreso=datetime.date(previo, 12, 15),
                tipo_salida="egreso")
            PromocionEstudiante.objects.create(proceso=proceso, estudiante=e, curso_origen=cuarto, resultado="egresa")
        repitente = Estudiante.objects.filter(curso=cursos["3B"]).order_by("pk").first()
        PromocionEstudiante.objects.create(proceso=proceso, estudiante=repitente, curso_origen=tercero,
                                           curso_destino=cursos["3B"], resultado="repite")
        # El año en curso queda con los cursos terminales configurados (paso 1), listo para revisar.
        ProcesoPromocion.objects.create(anio=self.anio).cursos_terminales.set([cursos["4M"]])

    # ------------------------------------------------------------------------------------------------------ casos
    def _atencion(self, caso, profesional, dias, nota, tipo="individual", motivo="regulacion_emocional",
                  urgencia="baja", derivado="", acuerdos="", minutos=45, horas=0):
        return SesionSeguimiento.objects.create(
            caso=caso, profesional=profesional, fecha_hora=self.ahora - datetime.timedelta(days=dias, hours=horas),
            duracion_minutos=minutos, tipo_atencion=tipo, urgencia=urgencia, motivo=motivo, derivado_por=derivado,
            nota=nota, acuerdos=acuerdos)

    def _casos_y_atenciones(self, est):
        u, hoy, ahora = self.u, self.hoy, self.ahora
        martina, benjamin, florencia, agustin = est["Martina"], est["Benjamín"], est["Florencia"], est["Agustín"]
        der = Derivacion.objects.create(estudiante=martina, derivante=u["rodrigo"], fecha_hora=ahora - datetime.timedelta(days=90),
                                        motivo="Se observa aislamiento en recreos y baja participación en clases durante las "
                                               "últimas tres semanas. La estudiante comenta que no quiere venir al colegio.")
        caso1 = Caso.objects.create(estudiante=martina, tipo_proceso="seguimiento", responsable=u["camila"],
                                    estado="seguimiento", fecha_apertura=hoy - datetime.timedelta(days=88),
                                    tipo_atencion="Individual")
        der.caso = caso1
        der.save()
        self._atencion(caso1, u["camila"], 85, "Primera entrevista. Martina relata dificultades para integrarse a un nuevo "
                       "grupo de amistades.", motivo="relaciones_pares", derivado="profesor_jefe",
                       acuerdos="Espacio semanal de conversación; observar recreos con la asistente de aula.")
        self._atencion(caso1, u["camila"], 60, "Se entrevista a la apoderada. Se acuerdan rutinas de apoyo en casa y "
                       "comunicación quincenal con el colegio.", tipo="familiar", motivo="familiar", minutos=60,
                       acuerdos="La apoderada acompañará la rutina de tareas; nueva reunión en un mes.")
        self._atencion(caso1, u["camila"], 30, "Refiere avances: participó dos veces en el taller de ajedrez y almuerza con "
                       "dos compañeras. Se mantiene el seguimiento quincenal.", motivo="relaciones_pares",
                       acuerdos="Seguir asistiendo al taller.")
        self._atencion(caso1, u["camila"], 8, "Entrevista de cierre de etapa. La estudiante se muestra tranquila y motivada.",
                       acuerdos="Coordinar con el profesor jefe actividades en grupos pequeños.")
        Hito.objects.create(caso=caso1, tipo="objetivo", fecha=hoy - datetime.timedelta(days=85), visible_profesor_jefe=True,
                            descripcion="Favorecer la integración de la estudiante en su grupo curso.")
        Hito.objects.create(caso=caso1, tipo="logro", fecha=hoy - datetime.timedelta(days=30), visible_profesor_jefe=True,
                            descripcion="Participa de forma regular en el taller de ajedrez.")
        Hito.objects.create(caso=caso1, tipo="hallazgo", fecha=hoy - datetime.timedelta(days=60),
                            descripcion="La dificultad se asocia al cambio de curso del año anterior.")

        # Caso PIE con evaluación cerrada cuya reevaluación ya venció (Benjamín) y plan PACI vigente
        caso2 = Caso.objects.create(estudiante=benjamin, tipo_proceso="pie_nee", responsable=u["marcela"], estado="seguimiento",
                                    fecha_apertura=sumar_anios(hoy, -2) - datetime.timedelta(days=40))
        ev = EvaluacionDiagnostica.objects.create(caso=caso2, tipo_nee="Trastorno específico del lenguaje",
                                                  fecha_evaluacion=sumar_anios(hoy, -2) - datetime.timedelta(days=20),
                                                  diagnostico="Evaluación integral fonoaudiológica y psicopedagógica con "
                                                              "resultados compatibles con NEE transitoria del lenguaje.")
        ev.fecha_reevaluacion = sumar_anios(ev.fecha_evaluacion, 2)
        ev.save()
        ParticipacionEvaluacion.objects.create(evaluacion=ev, usuario=u["marcela"], rol_profesional="Coordinadora PIE",
                                               aporte="Coordinación del proceso y aplicación de pruebas pedagógicas.",
                                               fecha=ev.fecha_evaluacion)
        ParticipacionEvaluacion.objects.create(evaluacion=ev, usuario=u["javiera"], rol_profesional="Psicóloga",
                                               aporte="Evaluación del desarrollo socioemocional.", fecha=ev.fecha_evaluacion)
        ev.estado = "cerrada"
        ev.save()
        PlanApoyo.objects.create(estudiante=benjamin, evaluacion=ev, tipo="paci", fecha_inicio=ev.fecha_evaluacion,
                                 adecuaciones="Instrucciones breves y apoyadas con imágenes; más tiempo en evaluaciones escritas.",
                                 detalle="Apoyo fonoaudiológico semanal en aula de recursos.")
        self._atencion(caso2, u["javiera"], 12, "Seguimiento del plan de apoyo con el estudiante: se muestra motivado con "
                       "las actividades del aula de recursos.", motivo="seguimiento_pie", derivado="pie")

        # Caso TEA abierto (Agustín) y derivación pendiente (Florencia)
        Caso.objects.create(estudiante=agustin, tipo_proceso="tea", responsable=u["javiera"],
                            fecha_apertura=hoy - datetime.timedelta(days=12))
        Derivacion.objects.create(estudiante=florencia, derivante=u["rodrigo"], fecha_hora=ahora - datetime.timedelta(days=2),
                                  motivo="Ha faltado reiteradamente durante el mes y llega sin materiales. La apoderada no "
                                         "ha respondido las citaciones.")

        # Dos casos con urgencia alta en su última atención («Casos urgentes») y atenciones de este mes
        vicente, antonia = est["Vicente"], est["Antonia"]
        caso3 = Caso.objects.create(estudiante=vicente, tipo_proceso="seguimiento", responsable=u["camila"],
                                    estado="seguimiento", fecha_apertura=hoy - datetime.timedelta(days=20))
        self._atencion(caso3, u["camila"], 18, "El estudiante consulta por estrés ante las evaluaciones de fin de semestre.",
                       motivo="ansiedad", derivado="estudiante", acuerdos="Técnicas de organización del estudio.")
        self._atencion(caso3, u["camila"], 1, "Se observa desánimo marcado y aislamiento. Se contacta a la familia el mismo "
                       "día y se coordina seguimiento cercano.", motivo="animo", urgencia="alta", derivado="profesor_jefe",
                       acuerdos="Entrevista con la familia esta semana; seguimiento diario con el profesor jefe.", minutos=60)
        caso4 = Caso.objects.create(estudiante=antonia, tipo_proceso="seguimiento", responsable=u["daniela"],
                                    estado="seguimiento", fecha_apertura=hoy - datetime.timedelta(days=6))
        self._atencion(caso4, u["daniela"], 0, "Conflicto familiar reciente que afecta la asistencia. Se activa apoyo de la "
                       "dupla psicosocial.", tipo="familiar", motivo="familiar", urgencia="alta", derivado="inspectoria",
                       acuerdos="Visita domiciliaria y red de apoyo comunal.", horas=2)
        self._atencion(caso1, u["camila"], 0, "Control breve: la estudiante mantiene los avances.", minutos=15, horas=3)

    def _alertas(self, est, sedes):
        u, ahora = self.u, self.ahora
        tomas, emilia = est["Tomás"], est["Emilia"]
        alerta = AlertaRiesgo.objects.create(estudiante=tomas, sede=sedes["Básica"], tipo_situacion="vulneracion_derechos",
                                             descripcion="El estudiante llega en varias ocasiones sin almuerzo y comenta que "
                                                         "pasa las tardes solo en su casa.",
                                             fecha_hora_conocimiento=ahora - datetime.timedelta(hours=30),
                                             fecha_hora_registro=ahora - datetime.timedelta(hours=29), informante=u["rodrigo"])
        notificar_alerta(alerta)
        gestion = GestionAlerta.objects.create(alerta=alerta, responsable=u["daniela"], accion="protocolo_activado",
                                               fecha_hora=ahora - datetime.timedelta(hours=26),
                                               detalle="Se activa el protocolo de vulneración de derechos y se cita a la apoderada.")
        activar_desde_alerta(alerta, u["daniela"], timezone.localtime(gestion.fecha_hora).date())
        alerta.estado = "en_gestion"
        alerta.save()
        alerta2 = AlertaRiesgo.objects.create(estudiante=emilia, sede=sedes["Básica"], tipo_situacion="violencia_maltrato",
                                              subtipo_violencia="entre_estudiantes",
                                              descripcion="Durante el recreo se observa a dos estudiantes empujando "
                                                          "reiteradamente a la estudiante junto a la escalera.",
                                              fecha_hora_conocimiento=ahora - datetime.timedelta(hours=3),
                                              fecha_hora_registro=ahora - datetime.timedelta(hours=2), informante=u["rodrigo"])
        notificar_alerta(alerta2)

    # ------------------------------------------------------------------------------------------------------ convivencia
    def _convivencia(self, cursos):
        u, rnd = self.u, self.rnd
        activos = list(Estudiante.objects.filter(curso__anio_escolar=self.anio).activos().select_related("curso"))
        # Más anotaciones desde 5° Básico, como en el prototipo.
        peso = {c: (1 if c in ("PK", "K", "1B", "2B", "3B", "4B") else 4) for c, _ in CURSOS}
        registradores = [u["rodrigo"], u["patricia"], u["daniela"]]
        for _ in range(170):
            e = rnd.choices(activos, weights=[peso[x.curso.nivel] for x in activos])[0]
            tipo = rnd.choices(["positiva", "moderada", "grave", "gravisima"], weights=[55, 30, 13, 2])[0]
            Anotacion.objects.create(estudiante=e, fecha=self._fecha_en_anio(), tipo=tipo,
                                     descripcion=rnd.choice(DESCRIPCIONES_ANOTACION[tipo]),
                                     registrada_por=rnd.choice(registradores))
        # Conflictos y mediaciones (básica 1°–6° y media 7°–4°)
        for j in range(14):
            nivel = rnd.choice(["3B", "4B", "5B", "6B", "7B", "8B", "1M", "2M"])
            del_curso = [e for e in activos if e.curso.nivel == nivel]
            tipo = "mediacion" if j % 3 else rnd.choice(["negociacion", "dialogo", "arbitraje"])
            resultado = rnd.choice(["con_acuerdo", "con_acuerdo", "en_proceso", "sin_acuerdo"])
            c = Conflicto.objects.create(
                fecha=self._fecha_en_anio(), tipo_gestion=tipo, curso=cursos[nivel], encargada=u["daniela"],
                descripcion="Discusión entre estudiantes del curso por un malentendido en el trabajo grupal, que escaló a "
                            "burlas en el recreo.", resultado=resultado,
                acuerdos="Los estudiantes acuerdan conversar con respeto y avisar a un adulto si vuelve a ocurrir."
                if resultado == "con_acuerdo" else "")
            c.participantes.set(rnd.sample(del_curso, min(len(del_curso), rnd.randint(2, 4))))
        # Situación conductual
        primero = [e for e in activos if e.curso.nivel == "1B"]
        registros = [(primero[0], "conductual", None, "Dificultad para respetar turnos en clase; se conversa con el estudiante."),
                     (primero[1], "conductual", None, "Se levanta reiteradamente del puesto durante las actividades."),
                     (primero[0], "asistencia", 78, "Asistencia del semestre bajo lo esperado; se cita al apoderado."),
                     ([e for e in activos if e.curso.nivel == "7B"][0], "academica", None,
                      "Baja en calificaciones de Matemática; se coordina apoyo con el docente."),
                     ([e for e in activos if e.curso.nivel == "1M"][0], "atrasos", None, "Cuatro atrasos en el mes.")]
        for e, categoria, pct, texto in registros:
            RegistroConductual.objects.create(estudiante=e, fecha=self._fecha_en_anio(), categoria=categoria,
                                              porcentaje_asistencia=pct, descripcion=texto, registrado_por=u["patricia"])
        # Protocolo cerrado del prototipo (conducta suicida, 2° Medio A)
        fecha = max(self.inicio_anio, datetime.date(self.anio, 4, 28)) if self.hoy > datetime.date(self.anio, 5, 30) \
            else self.hoy - datetime.timedelta(days=30)
        ProtocoloActivado.objects.create(
            protocolo="conducta_suicida", fecha_activacion=fecha, curso=cursos["2M"], responsable=u["camila"],
            estado="cerrado", fecha_cierre=fecha + datetime.timedelta(days=21),
            observaciones="Se aplicó el protocolo: contención, comunicación con la familia y derivación a la red de salud. "
                          "Seguimiento semanal por cuatro semanas y cierre coordinado con el equipo.")

    def _plan(self):
        u = self.u
        for dias, titulo, medio in ACTIVIDADES_PLAN:
            ActividadPlan.objects.create(tipo="actividad", titulo=titulo, fecha=self.hoy - datetime.timedelta(days=dias),
                                         responsable=u["daniela"], medio_verificacion=medio, estado="realizada",
                                         descripcion="Actividad del plan de gestión de convivencia escolar.")
        ActividadPlan.objects.create(tipo="taller", titulo="Taller de resolución pacífica de conflictos para 7° y 8°",
                                     fecha=self.hoy + datetime.timedelta(days=14), responsable=u["daniela"],
                                     medio_verificacion="Lista de asistencia", estado="pendiente")
        ActividadPlan.objects.create(tipo="reunion", titulo="Jornada de convivencia con apoderados",
                                     fecha=self.hoy + datetime.timedelta(days=30), responsable=u["daniela"], estado="pendiente")
