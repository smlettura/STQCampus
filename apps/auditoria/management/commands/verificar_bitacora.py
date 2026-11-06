from django.core.management.base import BaseCommand, CommandError

from apps.auditoria.servicios import verificar_cadena


class Command(BaseCommand):
    help = "Recalcula la cadena de hashes de la bitácora y detecta alteraciones."

    def handle(self, *args, **options):
        integra, id_roto, total = verificar_cadena()
        if not integra:
            raise CommandError("La cadena se rompe en el evento %d (de %d revisados)." % (id_roto, total))
        self.stdout.write(self.style.SUCCESS("Bitácora íntegra: %d eventos verificados." % total))
