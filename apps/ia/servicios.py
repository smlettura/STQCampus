"""Copiloto de IA (RF-16 a RF-19, RNF-11): cola de solicitudes atendida por el agente del equipo propio.

Flujo (sección 9.1.6 y Anexo G del informe):
1. La profesional elige estudiante, atenciones, tipo y secciones. La plataforma verifica permiso y consentimiento
   «uso_ia», arma el texto, lo seudonimiza (si queda un identificador, se bloquea) y deja la solicitud «pendiente», con
   el texto y la tabla de correspondencia cifrados en la base.
2. El agente del equipo propio la toma por HTTPS con su token («en_proceso», 10 minutos de plazo), la pasa a Ollama y
   devuelve el borrador. Tras 3 intentos fallidos queda en «error»; si nadie la toma en 24 horas, «expirada».
3. La plataforma reidentifica el borrador y lo guarda cifrado como ContenidoIA (etiqueta IA, estado «generado»), con
   el registro de la llamada (LlamadaModelo: solo el hash de lo enviado).
4. La profesional lo revisa, edita y valida (RF-18): se crea un Informe en borrador vinculado. O lo descarta. En ambos
   casos se borran el texto seudonimizado y la tabla de correspondencia.
"""
import datetime
import hashlib
import secrets

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.auditoria.servicios import registrar
from apps.cumplimiento.models import Consentimiento

from . import instrucciones
from .models import AgenteIA, ContenidoIA, LlamadaModelo, RetroalimentacionIA, SolicitudIA
from .seudonimizacion import Seudonimizador, SeudonimizacionIncompleta, reidentificar

DISPONIBLE = getattr(settings, "IA_HABILITADA", True)
MODELO = getattr(settings, "IA_MODELO", "stq-copiloto")
PLAZO_TOMA = datetime.timedelta(minutes=10)
MAX_INTENTOS = 3
EXPIRACION = datetime.timedelta(hours=24)
LATIDO_MAXIMO = datetime.timedelta(minutes=5)
MAX_CARACTERES_RESPUESTA = 30_000

TIPOS_INFORME = [("atencion", "Informe de atención"), ("derivacion_externa", "Derivación externa"),
                 ("apoderado", "Informe para apoderado"), ("direccion", "Informe para dirección")]
SECCIONES = [("antecedentes", "Antecedentes"), ("desarrollo", "Desarrollo de las sesiones"),
             ("acuerdos", "Acuerdos y compromisos"), ("sugerencias", "Sugerencias de seguimiento")]
SECCIONES_POR_DEFECTO = ("antecedentes", "desarrollo", "acuerdos")
PERIODOS = [(1, "Último mes"), (3, "Últimos 3 meses"), (6, "Últimos 6 meses"), (12, "Último año")]


class ErrorSolicitud(Exception):
    """La solicitud no se puede crear (el mensaje se muestra a la profesional)."""


class ModuloIANoDisponible(ErrorSolicitud):
    pass


def huella(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ agente y disponibilidad
def emitir_token(nombre):
    """Crea (o renueva) el token de un agente. Devuelve el valor en claro: se muestra una sola vez."""
    token = secrets.token_urlsafe(32)                     # 256 bits
    agente, _ = AgenteIA.objects.update_or_create(nombre=nombre, defaults={
        "hash_token": huella(token), "activo": True, "fecha_emision": timezone.now()})
    registrar(None, "modificacion", "agente_ia", agente.pk, detalle="token emitido")
    return agente, token


def agente_por_token(token):
    if not token:
        return None
    return AgenteIA.objects.filter(hash_token=huella(token), activo=True).first()


def agente_conectado():
    return AgenteIA.objects.filter(activo=True, ultimo_latido__gte=timezone.now() - LATIDO_MAXIMO).exists()


def latido(agente, modelo=""):
    agente.ultimo_latido = timezone.now()
    agente.modelo = (modelo or agente.modelo)[:60]
    agente.save(update_fields=["ultimo_latido", "modelo"])
    return SolicitudIA.objects.filter(estado="pendiente").count()


# ------------------------------------------------------------------ creación (lado de la profesional)
def crear_solicitud(usuario, estudiante, caso, sesiones, tipo, secciones):
    if not DISPONIBLE:
        raise ModuloIANoDisponible("El copiloto está deshabilitado en esta instalación.")
    if tipo not in dict(TIPOS_INFORME):
        raise ErrorSolicitud("Tipo de informe no válido.")
    secciones = [s for s, _ in SECCIONES if s in secciones]
    if not secciones:
        raise ErrorSolicitud("Elija al menos una sección.")
    if not sesiones:
        raise ErrorSolicitud("Elija al menos una atención.")
    if not Consentimiento.vigente_para(estudiante, "uso_ia"):
        raise ErrorSolicitud("No hay un consentimiento vigente del apoderado para el uso del módulo de IA. "
                             "Redacte el informe de forma manual o registre el consentimiento.")
    profesionales = [usuario, *[s.profesional for s in sesiones], estudiante.curso.profesor_jefe]
    seud = Seudonimizador(estudiante, profesionales)
    texto = instrucciones.construir_entrada(estudiante, sesiones, tipo, secciones)
    try:
        seudonimizado = seud.aplicar(texto)
    except SeudonimizacionIncompleta:
        registrar(usuario, "acceso_denegado", "solicitud_ia", None, detalle="bloqueada: seudonimización incompleta")
        raise ErrorSolicitud("La solicitud se bloqueó porque quedaba un dato identificable después de seudonimizar. "
                             "No se envió nada. Revise las atenciones elegidas o redacte el informe de forma manual.")
    sol = SolicitudIA.objects.create(caso=caso, solicitante=usuario, tipo_informe=tipo, secciones=",".join(secciones),
                                     texto_seudonimizado=seudonimizado, correspondencia=seud.correspondencia(),
                                     hash_entrada=huella(seudonimizado))
    registrar(usuario, "creacion", "solicitud_ia", sol.pk, detalle="atenciones=%d tipo=%s" % (len(sesiones), tipo))
    return sol


# ------------------------------------------------------------------ cola (lado del agente)
def _limpiar(sol):
    sol.texto_seudonimizado = ""
    sol.correspondencia = ""


def mantener_cola(ahora=None):
    """Devuelve a la cola lo que venció su plazo, marca errores y expira lo que lleva 24 horas sin atenderse."""
    ahora = ahora or timezone.now()
    cambios = 0
    for sol in SolicitudIA.objects.filter(estado="en_proceso", fecha_toma__lt=ahora - PLAZO_TOMA):
        if sol.intentos >= MAX_INTENTOS:
            sol.estado, sol.detalle_error, sol.fecha_termino = "error", "sin respuesta del agente", ahora
            _limpiar(sol)
        else:
            sol.estado = "pendiente"
        sol.save()
        cambios += 1
    for sol in SolicitudIA.objects.filter(estado="pendiente", fecha_creacion__lt=ahora - EXPIRACION):
        sol.estado, sol.fecha_termino = "expirada", ahora
        _limpiar(sol)
        sol.save()
        registrar(None, "eliminacion", "solicitud_ia", sol.pk, detalle="expirada: texto seudonimizado borrado")
        cambios += 1
    return cambios


def tomar(agente):
    """Entrega al agente la solicitud pendiente más antigua (o None). Solo sale el texto seudonimizado."""
    mantener_cola()
    with transaction.atomic():
        sol = (SolicitudIA.objects.select_for_update().filter(estado="pendiente").order_by("fecha_creacion").first())
        if sol is None:
            return None
        sol.estado, sol.agente, sol.fecha_toma = "en_proceso", agente, timezone.now()
        sol.intentos += 1
        sol.save(update_fields=["estado", "agente", "fecha_toma", "intentos"])
    registrar(None, "exportacion", "solicitud_ia", sol.pk, detalle="tomada por agente %s; sha256=%s" % (agente.pk, sol.hash_entrada))
    return {"id": sol.pk, "modelo": MODELO,
            "mensajes": instrucciones.construir_mensajes(sol.texto_seudonimizado, sol.secciones.split(","))}


def _solicitud_del_agente(agente, id_solicitud):
    sol = SolicitudIA.objects.filter(pk=id_solicitud, agente=agente, estado="en_proceso").first()
    if sol is None:
        raise ErrorSolicitud("La solicitud no está en proceso para este agente.")
    return sol


def registrar_resultado(agente, id_solicitud, texto, modelo="", tokens_entrada=0, tokens_salida=0):
    texto = (texto or "").strip()
    if not texto:
        return registrar_error(agente, id_solicitud, "respuesta vacía")
    with transaction.atomic():
        sol = _solicitud_del_agente(agente, id_solicitud)
        borrador = reidentificar(texto[:MAX_CARACTERES_RESPUESTA], sol.correspondencia)
        contenido = ContenidoIA.objects.create(caso=sol.caso, solicitante=sol.solicitante, tipo="borrador_informe",
                                               modelo=(modelo or MODELO)[:60], texto_generado=borrador)
        LlamadaModelo.objects.create(contenido=contenido, proveedor="ollama (equipo propio)", modelo=(modelo or MODELO)[:60],
                                     tokens_entrada=max(0, int(tokens_entrada or 0)),
                                     tokens_salida=max(0, int(tokens_salida or 0)), hash_carga=sol.hash_entrada)
        sol.estado, sol.contenido, sol.fecha_termino = "lista", contenido, timezone.now()
        sol.save(update_fields=["estado", "contenido", "fecha_termino"])
    registrar(None, "creacion", "contenido_ia", contenido.pk, detalle="borrador recibido de la solicitud %s" % sol.pk)
    return sol


def registrar_error(agente, id_solicitud, detalle):
    sol = _solicitud_del_agente(agente, id_solicitud)
    if sol.intentos >= MAX_INTENTOS:
        sol.estado, sol.fecha_termino = "error", timezone.now()
        _limpiar(sol)
    else:
        sol.estado = "pendiente"
    sol.detalle_error = (detalle or "")[:200]
    sol.save()
    return sol


# ------------------------------------------------------------------ revisión humana (RF-18, RF-19)
TIPO_INFORME_FICHA = {"atencion": "seguimiento", "derivacion_externa": "seguimiento", "apoderado": "familia",
                      "direccion": "seguimiento"}


def validar(usuario, contenido, texto_final, tipo_ficha=None):
    """La profesional valida el borrador editado: queda registro de quién y cuándo, y se crea un Informe en borrador."""
    from apps.evaluacion.models import Informe
    texto_final = (texto_final or "").strip()
    if len(texto_final) < 20:
        raise ErrorSolicitud("El texto validado está vacío o es demasiado corto.")
    sol = getattr(contenido, "solicitud", None)
    with transaction.atomic():
        contenido.estado, contenido.validador, contenido.fecha_validacion = "validado", usuario, timezone.now()
        contenido.texto_validado = texto_final
        contenido.save()
        tipo = tipo_ficha if tipo_ficha in dict(Informe.TIPOS) else TIPO_INFORME_FICHA.get(sol.tipo_informe if sol else "", "seguimiento")
        informe = Informe.objects.create(caso=contenido.caso, tipo=tipo, contenido=texto_final, contenido_ia=contenido)
        if sol is not None:
            sol.estado = "cerrada"
            _limpiar(sol)
            sol.save()
    registrar(usuario, "modificacion", "contenido_ia", contenido.pk, detalle="validado; informe %s" % informe.pk)
    return informe


def descartar(usuario, contenido):
    sol = getattr(contenido, "solicitud", None)
    contenido.estado = "descartado"
    contenido.save(update_fields=["estado"])
    if sol is not None:
        sol.estado = "cerrada"
        _limpiar(sol)
        sol.save()
    registrar(usuario, "modificacion", "contenido_ia", contenido.pk, detalle="descartado")


def retroalimentar(usuario, contenido, motivo, comentario):
    r = RetroalimentacionIA(contenido=contenido, profesional=usuario, motivo=motivo, comentario=comentario)
    r.full_clean()
    r.save()
    registrar(usuario, "creacion", "retroalimentacion_ia", r.pk)
    return r
