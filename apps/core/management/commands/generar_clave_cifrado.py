import base64
import os

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Genera una clave AES-256 para CIFRADO_CLAVES (guárdela en AWS Secrets Manager, nunca en el repositorio)."

    def add_arguments(self, parser):
        parser.add_argument("--id", default="k1", help="Identificador de la clave (para rotación).")

    def handle(self, *args, **options):
        clave = base64.urlsafe_b64encode(os.urandom(32)).decode()
        self.stdout.write("CIFRADO_CLAVES=%s:%s" % (options["id"], clave))
