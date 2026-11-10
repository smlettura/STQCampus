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

from . import guardas, instrucciones, motor
from .models import AgenteIA, ContenidoIA, LlamadaModelo, RetroalimentacionIA, SolicitudIA
from .seudonimizacion import Seudonimizador, SeudonimizacionIncompleta, reidentificar

DISPONIBLE = getattr(settings, "IA_HABILITADA", True)
MODELO = getattr(settings, "IA_MODELO", "stq-copiloto")
PLAZO_TOMA = datetime.timedelta(minutes=20)          # en CPU un borrador tarda 1-3 min; con reintento, el doble
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
def crear_solicitud(usuario, estudiante, caso, sesiones, tipo, secciones, indicaciones="", otros_nombres=()):
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
    indicaciones = (indicaciones or "").strip()[:500]
    pedidos = guardas.detectar_peticiones(indicaciones)          # guardián de entrada: no se envía nada
    if pedidos:
        registrar(usuario, "acceso_denegado", "solicitud_ia", None,
                  detalle="bloqueada: indicación fuera de límites (%s)" % ",".join(h.codigo for h in pedidos))
        raise ErrorSolicitud("El asistente no puede: " + "; ".join(str(h) for h in pedidos)
                             + ". Quite esa indicación o redacte esa parte usted. " + guardas.AYUDA_FORMATOS)
    condiciones, ignoradas = guardas.filtrar_condiciones(indicaciones) if indicaciones else ("Ninguna.", [])
    entrada = instrucciones.construir_entrada(sesiones, tipo, secciones, condiciones)
    entrada, inyecciones = guardas.neutralizar_inyecciones(entrada)
    profesionales = [usuario, *[s.profesional for s in sesiones], estudiante.curso.profesor_jefe]
    seud = Seudonimizador(estudiante, profesionales, otros_nombres=otros_nombres)
    try:
        seudonimizado = seud.aplicar(entrada)
    except SeudonimizacionIncompleta:
        registrar(usuario, "acceso_denegado", "solicitud_ia", None, detalle="bloqueada: seudonimización incompleta")
        raise ErrorSolicitud("La solicitud se bloqueó porque quedaba un dato identificable después de seudonimizar. "
                             "No se envió nada. Revise las atenciones elegidas o redacte el informe de forma manual.")
    avisos = ["Se ignoró una indicación que no es de formato: «%s». %s" % (h.fragmento[:70], guardas.AYUDA_FORMATOS)
              for h in ignoradas]
    avisos += ["Se omitió una instrucción dirigida al asistente dentro de las notas: %s" % h.fragmento.strip()[:70]
               for h in inyecciones]
    sol = SolicitudIA.objects.create(caso=caso, solicitante=usuario, tipo_informe=tipo, secciones=",".join(secciones),
                                     texto_seudonimizado=seudonimizado, correspondencia=seud.correspondencia(),
                                     hash_entrada=huella(seudonimizado), avisos="\n".join(avisos))
    registrar(usuario, "creacion", "solicitud_ia", sol.pk, detalle="atenciones=%d tipo=%s prompt=%s inyecciones=%d" % (
        len(sesiones), tipo, instrucciones.VERSION_PROMPT, len(inyecciones)))
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
    return _trabajo(sol, instrucciones.construir_mensajes(sol.texto_seudonimizado))


def _trabajo(sol, mensajes):
    return {"id": sol.pk, "modelo": MODELO, "mensajes": mensajes, "opciones": instrucciones.opciones(),
            "keep_alive": getattr(settings, "IA_KEEP_ALIVE", "60m")}


def _solicitud_del_agente(agente, id_solicitud):
    sol = SolicitudIA.objects.filter(pk=id_solicitud, agente=agente, estado="en_proceso").first()
    if sol is None:
        raise ErrorSolicitud("La solicitud no está en proceso para este agente.")
    return sol


def registrar_resultado(agente, id_solicitud, texto, modelo="", tokens_entrada=0, tokens_salida=0):
    """Guardián de salida (guardas.py) sobre lo que devolvió el modelo. Si se sale de los límites y aún no se reintentó,
    devuelve un trabajo nuevo con el aviso correctivo (el agente lo vuelve a generar dentro del mismo plazo). Si
    persiste, el borrador queda «bloqueado» y no se puede validar. Devuelve (solicitud, trabajo_reintento | None)."""
    texto = (texto or "").strip()[:MAX_CARACTERES_RESPUESTA]
    if not texto:
        return registrar_error(agente, id_solicitud, "respuesta vacía"), None
    with transaction.atomic():
        sol = _solicitud_del_agente(agente, id_solicitud)
        entrada = sol.texto_seudonimizado
        secciones = instrucciones.texto_secciones(sol.secciones.split(","))
        infr = guardas.revisar_limites(guardas.sin_condiciones(entrada), texto, entrada)
        infr += guardas.secciones_ajenas(texto, secciones, extra=(instrucciones.TITULOS_TIPO.get(sol.tipo_informe, ""),))
        if infr and not sol.reintentado:
            sol.reintentado, sol.fecha_toma = True, timezone.now()
            sol.save(update_fields=["reintentado", "fecha_toma"])
            registrar(None, "exportacion", "solicitud_ia", sol.pk, detalle="reintento correctivo: %s" % ",".join(h.codigo for h in infr))
            return sol, _trabajo(sol, instrucciones.construir_mensajes(entrada, instrucciones.aviso_reintento(infr)))
        quitadas = []
        if infr and all(h.codigo == guardas.SECCION for h in infr):
            quitadas, texto, infr = infr, guardas.quitar_secciones(texto, infr), []
        alertas = [a for a in sol.avisos.split("\n") if a]
        if infr:
            estado, borrador = "bloqueado", motor.MENSAJE_BLOQUEO
            alertas += ["Bloqueado: %s" % h for h in infr]
        else:
            estado = "generado"
            alertas += motor.revisar_salida(entrada + "\n[ESTUDIANTE]", texto)   # el estudiante siempre es el sujeto
            if "[PENDIENTE" in texto.upper():
                alertas.append("Hay partes marcadas [PENDIENTE]: faltaba información en las atenciones elegidas. "
                               "Complételas o bórrelas antes de validar el informe.")
            alertas += ["Se eliminó una sección que no se había pedido: %s" % h.fragmento.strip()[:70] for h in quitadas]
            omit = guardas.omisiones_riesgo(entrada, texto)
            if omit:
                alertas.append("El borrador no menciona datos de riesgo que están en las notas (%s): revíselo." % ", ".join(omit))
            if guardas.MARCA_FUERA_DE_ALCANCE.lower() in texto.lower():
                alertas.append("El asistente se negó a redactar una parte («FUERA DE MI ALCANCE»): complete esa parte usted.")
            nuevas = guardas.cifras_nuevas(entrada, texto)
            if nuevas:
                alertas.append("Cifras que no estaban en las notas (verifique): " + ", ".join(nuevas[:8]))
            borrador = reidentificar(texto, sol.correspondencia)
        contenido = ContenidoIA.objects.create(caso=sol.caso, solicitante=sol.solicitante, tipo="borrador_informe",
                                               modelo=(modelo or MODELO)[:60], texto_generado=borrador, estado=estado,
                                               alertas="\n".join(alertas))
        LlamadaModelo.objects.create(contenido=contenido, proveedor="ollama (equipo propio)", modelo=(modelo or MODELO)[:60],
                                     tokens_entrada=max(0, int(tokens_entrada or 0)),
                                     tokens_salida=max(0, int(tokens_salida or 0)), hash_carga=sol.hash_entrada)
        sol.estado, sol.contenido, sol.fecha_termino = "lista", contenido, timezone.now()
        if estado == "bloqueado":
            _limpiar(sol)
        sol.save()
    registrar(None, "creacion", "contenido_ia", contenido.pk, detalle="borrador %s de la solicitud %s; prompt %s; reintento=%s; %s" % (
        estado, sol.pk, instrucciones.VERSION_PROMPT, sol.reintentado, ",".join(h.codigo for h in infr)))
    return sol, None


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
