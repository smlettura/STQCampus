#!/usr/bin/env python3
"""Agente del copiloto STQCampus: corre en el PC del equipo de IA, junto a Ollama.

Solo hace conexiones SALIENTES (no abre puertos): pregunta a la plataforma por HTTPS si hay solicitudes, toma una,
la pasa a Ollama en 127.0.0.1 y devuelve el borrador. Lo que recibe ya viene seudonimizado ([ESTUDIANTE], [CURSO]…).
No guarda nada en disco y no registra el texto de las solicitudes en el log.

Configuración (variables de entorno o archivo agente.env junto al script):
    STQ_URL       https://su-dominio            (obligatoria)
    STQ_TOKEN     token de `manage.py crear_token_agente`   (obligatoria)
    OLLAMA_URL    http://127.0.0.1:11434        (por defecto)
    MODELO        stq-copiloto                  (si la plataforma indica otro modelo, se usa el de la plataforma)
    ESPERA        10                            (segundos entre consultas cuando la cola está vacía)
    TIMEOUT_OLLAMA 900                          (segundos máximos por borrador; en CPU tarda 1-3 min)
    LOG_ARCHIVO   agente.log                    (opcional; sin él, el log va a la consola)

Solo usa la biblioteca estándar de Python 3.9+: no hay que instalar nada.
"""
import json
import logging
import os
import signal
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

VERSION = "1.0"
log = logging.getLogger("agente_stq")


def cargar_env(ruta):
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            k, v = linea.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


cargar_env(Path(__file__).with_name("agente.env"))
STQ_URL = os.environ.get("STQ_URL", "").rstrip("/")
STQ_TOKEN = os.environ.get("STQ_TOKEN", "")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
MODELO = os.environ.get("MODELO", "stq-copiloto")
ESPERA = int(os.environ.get("ESPERA", "10"))
TIMEOUT_OLLAMA = int(os.environ.get("TIMEOUT_OLLAMA", "900"))
LATIDO_CADA = 60
seguir = True


def _http(metodo, url, cuerpo=None, cabeceras=None, timeout=30):
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, method=metodo,
                                 headers={"Content-Type": "application/json", "User-Agent": "agente-stq/" + VERSION,
                                          **(cabeceras or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        texto = r.read().decode("utf-8")
        return r.status, (json.loads(texto) if texto else None)


def plataforma(ruta, cuerpo=None):
    return _http("POST", STQ_URL + "/ia/agente/" + ruta, cuerpo or {}, {"Authorization": "Bearer " + STQ_TOKEN})


def ollama_disponible():
    try:
        _, datos = _http("GET", OLLAMA_URL + "/api/tags", timeout=5)
        nombres = {m.get("name", "").split(":")[0] for m in (datos or {}).get("models", [])}
        if MODELO.split(":")[0] not in nombres:
            log.warning("Ollama responde, pero no tiene el modelo %s (tiene: %s)", MODELO, ", ".join(sorted(nombres)) or "ninguno")
            return False
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("Ollama no responde en %s: %s", OLLAMA_URL, e)
        return False


def generar(modelo, mensajes, opciones=None, keep_alive=None):
    cuerpo = {"model": modelo, "messages": mensajes, "stream": False}
    if opciones:
        cuerpo["options"] = opciones          # temperature, num_ctx, num_predict, num_gpu: los indica la plataforma
    if keep_alive:
        cuerpo["keep_alive"] = keep_alive
    _, r = _http("POST", OLLAMA_URL + "/api/chat", cuerpo, timeout=TIMEOUT_OLLAMA)
    return (r.get("message") or {}).get("content", ""), r.get("prompt_eval_count", 0), r.get("eval_count", 0)


def atender(trabajo):
    """Genera y devuelve. Si el guardián de la plataforma rechaza la salida, responde con un trabajo de reintento
    (con un aviso correctivo) y se genera una sola vez más."""
    sid = trabajo["id"]
    t0 = time.monotonic()
    for _ in range(2):
        modelo = trabajo.get("modelo") or MODELO
        log.info("Solicitud %s: generando con %s…", sid, modelo)
        try:
            texto, te, ts = generar(modelo, trabajo["mensajes"], trabajo.get("opciones"), trabajo.get("keep_alive"))
            cuerpo = {"texto": texto, "modelo": modelo, "tokens_entrada": te, "tokens_salida": ts}
        except Exception as e:  # noqa: BLE001  (se informa a la plataforma, que reintenta hasta 3 veces)
            log.error("Solicitud %s: fallo de Ollama: %s", sid, e)
            cuerpo = {"error": "fallo de Ollama: %s" % type(e).__name__}
        _, resp = plataforma("%s/resultado/" % sid, cuerpo)
        if not (resp or {}).get("reintentar"):
            break
        log.info("Solicitud %s: la plataforma pidió una versión corregida", sid)
        trabajo = resp["reintentar"]
    log.info("Solicitud %s devuelta (%s) en %.0f s", sid, "error" if "error" in cuerpo else "borrador", time.monotonic() - t0)


def ciclo():
    ultimo_latido = 0.0
    while seguir:
        try:
            if not ollama_disponible():
                time.sleep(30)          # sin Ollama no se toma nada: la plataforma muestra «equipo de IA apagado»
                continue
            status, trabajo = plataforma("tomar/", {"modelo": MODELO})   # también cuenta como latido
            ultimo_latido = time.monotonic()
            if status == 200 and trabajo:
                atender(trabajo)
                continue
        except urllib.error.HTTPError as e:
            if e.code == 401:
                log.critical("La plataforma rechazó el token (401). Emita uno nuevo con crear_token_agente.")
                return 2
            log.warning("La plataforma respondió %s; reintento en %s s", e.code, ESPERA * 3)
            time.sleep(ESPERA * 3)
            continue
        except Exception as e:  # noqa: BLE001  (red caída, DNS, etc.)
            log.warning("Sin conexión con la plataforma: %s", e)
            time.sleep(ESPERA * 3)
            continue
        if time.monotonic() - ultimo_latido > LATIDO_CADA:
            plataforma("latido/", {"modelo": MODELO})
        time.sleep(ESPERA)
    return 0


def detener(*_):
    global seguir
    seguir = False
    log.info("Deteniendo el agente…")


def main():
    archivo = os.environ.get("LOG_ARCHIVO")          # en Windows con pythonw no hay consola: use un archivo
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        **({"filename": archivo, "encoding": "utf-8"} if archivo else {}))
    if not STQ_URL.startswith("https://") and not STQ_URL.startswith("http://127.0.0.1"):
        log.critical("STQ_URL debe ser https://… (solo se acepta http para pruebas en 127.0.0.1).")
        return 2
    if not STQ_TOKEN:
        log.critical("Falta STQ_TOKEN.")
        return 2
    signal.signal(signal.SIGINT, detener)
    signal.signal(signal.SIGTERM, detener)
    if "--probar" in sys.argv:
        ok = ollama_disponible()
        status, datos = plataforma("latido/", {"modelo": MODELO})
        log.info("Ollama: %s · Plataforma: %s %s", "OK" if ok else "FALLA", status, datos)
        return 0 if ok else 1
    log.info("Agente STQ %s · plataforma %s · Ollama %s · modelo %s", VERSION, STQ_URL, OLLAMA_URL, MODELO)
    return ciclo()


if __name__ == "__main__":
    sys.exit(main())
