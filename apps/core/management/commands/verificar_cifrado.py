"""Verificación periódica del cifrado (Ley 21.719, art. 14 quinquies: verificar y evaluar regularmente las medidas).

Revisa, sin mostrar ningún dato personal, que cada valor de las columnas cifradas tenga el formato esperado, que se
descifre con las claves cargadas y qué clave lo cifró (útil para completar una rotación). Con --adjuntos revisa además
que cada archivo adjunto y evidencia se descifre y conserve su huella SHA-256. Termina con error si algo falla.
"""
from collections import Counter

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.auditoria.servicios import registrar
from apps.core.campos import TextoCifrado
from apps.core.cifrado import VERSION, descifrar


def columnas_cifradas():
    for modelo in apps.get_models():
        for campo in modelo._meta.concrete_fields:
            if isinstance(campo, TextoCifrado):
                yield modelo, campo


def revisar_columna(modelo, campo):
    tabla, columna = modelo._meta.db_table, campo.column
    qn = connection.ops.quote_name
    r = {"columna": "%s.%s" % (tabla, columna), "con_valor": 0, "formato_invalido": 0, "no_descifra": 0, "claves": Counter()}
    with connection.cursor() as c:
        c.execute("SELECT %s FROM %s WHERE %s IS NOT NULL" % (qn(columna), qn(tabla), qn(columna)))
        for (valor,) in c.fetchall():
            valor = valor.encode() if isinstance(valor, str) else bytes(valor)
            if not valor:
                continue
            r["con_valor"] += 1
            if not valor.startswith(VERSION) or len(valor) < 2 + valor[1] + 28:
                r["formato_invalido"] += 1
                continue
            r["claves"][valor[2:2 + valor[1]].decode(errors="replace")] += 1
            try:
                descifrar(valor, campo.contexto())
            except Exception:
                r["no_descifra"] += 1
    return r


def revisar_adjuntos():
    from apps.casos.almacenamiento import leer_bytes
    from apps.casos.models import Documento
    from apps.convivencia.models import EvidenciaActividad
    total = errores = 0
    for modelo in (Documento, EvidenciaActividad):
        for ruta, huella in modelo.objects.values_list("ruta_objeto", "hash_sha256"):
            total += 1
            try:
                leer_bytes(ruta, huella)
            except Exception:
                errores += 1
    return total, errores


class Command(BaseCommand):
    help = ("Verifica que las columnas cifradas solo contengan texto cifrado válido y legible con las claves cargadas "
            "(y, con --adjuntos, los archivos). No muestra datos personales. Queda registrado en la bitácora.")

    def add_arguments(self, parser):
        parser.add_argument("--adjuntos", action="store_true", help="Revisa también los archivos adjuntos y evidencias.")

    def handle(self, *args, **o):
        problemas = valores = 0
        claves = Counter()
        self.stdout.write("Clave activa: %s · claves cargadas: %s" % (settings.CIFRADO_CLAVE_ACTIVA,
                                                                       ", ".join(settings.CIFRADO_CLAVES)))
        self.stdout.write("%-42s %9s %9s %9s  %s" % ("Columna", "Valores", "Formato", "Descifra", "Claves"))
        for modelo, campo in columnas_cifradas():
            r = revisar_columna(modelo, campo)
            valores += r["con_valor"]
            claves.update(r["claves"])
            malos = r["formato_invalido"] + r["no_descifra"]
            problemas += malos
            self.stdout.write("%-42s %9d %9s %9s  %s" % (
                r["columna"], r["con_valor"], "OK" if not r["formato_invalido"] else "%d mal" % r["formato_invalido"],
                "OK" if not r["no_descifra"] else "%d mal" % r["no_descifra"],
                ", ".join("%s=%d" % kv for kv in sorted(r["claves"].items())) or "—"))
        detalle = "verificación de cifrado: %d valores, %d con problemas" % (valores, problemas)
        if o["adjuntos"]:
            total, errores = revisar_adjuntos()
            problemas += errores
            self.stdout.write("Adjuntos y evidencias: %d revisados, %d con problemas." % (total, errores))
            detalle += "; adjuntos %d/%d con problemas" % (errores, total)
        antiguas = [k for k in claves if k != settings.CIFRADO_CLAVE_ACTIVA]
        if antiguas:
            self.stdout.write(self.style.WARNING("Hay valores cifrados con claves anteriores (%s): la rotación no ha "
                                                 "terminado; no retire esas claves todavía." % ", ".join(sorted(antiguas))))
        registrar(None, "consulta", "cifrado", None, detalle=detalle)
        if problemas:
            raise CommandError("Se encontraron %d valores o archivos con problemas de cifrado." % problemas)
        self.stdout.write(self.style.SUCCESS("Cifrado verificado: %d valores en %d columnas, sin problemas." % (
            valores, sum(1 for _ in columnas_cifradas()))))
