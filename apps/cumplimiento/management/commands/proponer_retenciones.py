from django.core.management.base import BaseCommand

from apps.cumplimiento.servicios import proponer_retenciones


class Command(BaseCommand):
    help = "Tarea mensual (RNF-10): propone a la Directora los expedientes con 15 años cumplidos. No elimina nada."

    def handle(self, *args, **options):
        n = proponer_retenciones()
        self.stdout.write(self.style.SUCCESS("%d propuestas de eliminación creadas." % n))
