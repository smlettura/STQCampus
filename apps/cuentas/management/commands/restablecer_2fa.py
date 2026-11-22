from django.core.management.base import BaseCommand, CommandError

from apps.auditoria.servicios import registrar
from apps.cuentas.models import Usuario


class Command(BaseCommand):
    help = ("Restablece el segundo factor de un usuario: en su próximo ingreso verá un QR nuevo. Útil si perdió el teléfono o "
            "borró la cuenta de la aplicación de autenticación. Queda registrado en la bitácora.")

    def add_arguments(self, parser):
        parser.add_argument("correo")

    def handle(self, *args, **o):
        usuario = Usuario.objects.filter(correo=o["correo"].strip().lower()).first()
        if usuario is None:
            raise CommandError("No existe un usuario con ese correo.")
        usuario.secreto_totp, usuario.mfa_activo = None, False
        usuario.save(update_fields=["secreto_totp", "mfa_activo"])
        registrar(None, "modificacion", "usuario", usuario.pk, detalle="segundo factor restablecido por comando")
        self.stdout.write(self.style.SUCCESS("Segundo factor restablecido para %s. En su próximo ingreso configurará uno "
                                             "nuevo con un código QR." % usuario.correo))
