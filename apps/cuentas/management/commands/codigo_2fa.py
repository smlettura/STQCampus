import pyotp
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.cuentas.models import Usuario


class Command(BaseCommand):
    help = "SOLO DESARROLLO: muestra el código TOTP vigente de un usuario de demostración."

    def add_arguments(self, parser):
        parser.add_argument("correo")

    def handle(self, *args, **o):
        if not settings.DEBUG:
            raise CommandError("Este comando solo funciona con DJANGO_DEBUG=1.")
        usuario = Usuario.objects.filter(correo=o["correo"].lower()).first()
        if not usuario or not usuario.secreto_totp:
            raise CommandError("El usuario no existe o aún no configura el segundo factor.")
        self.stdout.write(pyotp.TOTP(usuario.secreto_totp).now())
