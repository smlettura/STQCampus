"""Emite, renueva o revoca el token del agente del copiloto (equipo propio con Ollama).

    python manage.py crear_token_agente pc-equipo-ia          # emite o renueva; muestra el token UNA vez
    python manage.py crear_token_agente pc-equipo-ia --revocar
    python manage.py crear_token_agente --listar

En la base solo queda el hash SHA-256 del token. Si se pierde, se emite uno nuevo (el anterior deja de servir).
"""
from django.core.management.base import BaseCommand, CommandError

from apps.auditoria.servicios import registrar
from apps.ia import servicios
from apps.ia.models import AgenteIA


class Command(BaseCommand):
    help = "Emite, renueva o revoca el token del agente del copiloto de IA."

    def add_arguments(self, parser):
        parser.add_argument("nombre", nargs="?", help="nombre del agente, p. ej. pc-equipo-ia")
        parser.add_argument("--revocar", action="store_true", help="desactiva el agente (su token deja de servir)")
        parser.add_argument("--listar", action="store_true", help="lista los agentes y su último latido")

    def handle(self, *args, nombre=None, revocar=False, listar=False, **opts):
        if listar:
            for a in AgenteIA.objects.order_by("nombre"):
                self.stdout.write("%-24s %-8s último latido: %s  modelo: %s" % (
                    a.nombre, "activo" if a.activo else "revocado", a.ultimo_latido or "nunca", a.modelo or "-"))
            return
        if not nombre:
            raise CommandError("Indique el nombre del agente (o --listar).")
        if revocar:
            n = AgenteIA.objects.filter(nombre=nombre).update(activo=False)
            if not n:
                raise CommandError("No existe el agente %s." % nombre)
            registrar(None, "modificacion", "agente_ia", None, detalle="token revocado: %s" % nombre)
            self.stdout.write(self.style.SUCCESS("Agente %s revocado." % nombre))
            return
        agente, token = servicios.emitir_token(nombre)
        self.stdout.write(self.style.SUCCESS("Token del agente %s (se muestra UNA sola vez; guárdelo en el PC del equipo de IA):" % agente.nombre))
        self.stdout.write(token)
