"""Genera (o aplica) los permisos mínimos del usuario de base de datos de la aplicación en MySQL.

La aplicación se conecta con un usuario que puede leer y escribir las tablas del negocio, pero sobre la bitácora solo
tiene SELECT e INSERT: ni siquiera con acceso a la base se pueden modificar o borrar eventos desde la aplicación (RNF-03).
Las migraciones se ejecutan con otro usuario (propietario del esquema).
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

SOLO_INSERCION = {"evento_auditoria"}
SOLO_LECTURA = {"django_migrations", "django_content_type", "auth_permission"}


class Command(BaseCommand):
    help = "Imprime (o aplica con --aplicar) las sentencias GRANT del usuario de aplicación en MySQL."

    def add_arguments(self, parser):
        parser.add_argument("--usuario", default="bienestar_app")
        parser.add_argument("--host", default="%")
        parser.add_argument("--aplicar", action="store_true", help="Ejecuta las sentencias con la conexión actual.")

    def handle(self, *args, **o):
        if connection.vendor != "mysql":
            raise CommandError("Este comando es para MySQL (DB_ENGINE=mysql).")
        bd = settings.DATABASES["default"]["NAME"]
        destino = "'%s'@'%s'" % (o["usuario"], o["host"])
        sentencias = ["REVOKE ALL PRIVILEGES ON `%s`.* FROM %s" % (bd, destino)]
        for tabla in sorted(connection.introspection.table_names()):
            if tabla in SOLO_INSERCION:
                privilegios = "SELECT, INSERT"
            elif tabla in SOLO_LECTURA:
                privilegios = "SELECT"
            else:
                privilegios = "SELECT, INSERT, UPDATE, DELETE"
            sentencias.append("GRANT %s ON `%s`.`%s` TO %s" % (privilegios, bd, tabla, destino))
        if not o["aplicar"]:
            self.stdout.write("-- Ejecute como administrador de MySQL después de `migrate`.")
            for s in sentencias:
                self.stdout.write(s + ";")
            return
        with connection.cursor() as c:
            for s in sentencias:
                try:
                    c.execute(s)
                except Exception as e:  # REVOKE falla si el usuario aún no tenía privilegios a nivel de base
                    if not s.startswith("REVOKE"):
                        raise CommandError("%s -> %s" % (s, e))
        self.stdout.write(self.style.SUCCESS("Permisos aplicados a %s (%d tablas)." % (destino, len(sentencias) - 1)))
