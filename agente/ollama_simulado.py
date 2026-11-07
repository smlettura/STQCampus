#!/usr/bin/env python3
"""Ollama falso para pruebas del flujo (no es un modelo): responde /api/tags y /api/chat con un borrador fijo que
conserva los marcadores recibidos. Uso: python ollama_simulado.py [puerto]  (por defecto 11434)."""
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODELO = "stq-copiloto"


class Manejador(BaseHTTPRequestHandler):
    def _json(self, datos, status=200):
        cuerpo = json.dumps(datos).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        if self.path == "/api/tags":
            return self._json({"models": [{"name": MODELO + ":latest"}]})
        self._json({"error": "no encontrado"}, 404)

    def do_POST(self):
        if self.path != "/api/chat":
            return self._json({"error": "no encontrado"}, 404)
        datos = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        entrada = datos["messages"][-1]["content"]
        m = re.search(r"Secciones solicitadas \(en este orden\): (.+)", entrada)
        titulos = ["## " + t.strip() for t in (m.group(1).split(";") if m else ["Borrador"])]
        marcadores = sorted(set(re.findall(r"\[[A-Z_]+(?:_\d+)?\]", entrada.split("Notas de atencion", 1)[-1])))
        texto = "\n\n".join("%s\n[BORRADOR SIMULADO] Texto de prueba sobre %s." % (t, ", ".join(marcadores) or "el caso")
                            for t in titulos)
        self._json({"model": datos.get("model"), "message": {"role": "assistant", "content": texto}, "done": True,
                    "prompt_eval_count": len(entrada) // 4, "eval_count": len(texto) // 4})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 11434
    print("Ollama simulado en 127.0.0.1:%d" % puerto)
    ThreadingHTTPServer(("127.0.0.1", puerto), Manejador).serve_forever()
