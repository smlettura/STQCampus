from django.core.management.base import BaseCommand

from apps.cumplimiento.models import RetencionEliminacion
from apps.cumplimiento.servicios import ejecutar


class Command(BaseCommand):
    help = "Ejecuta solo las eliminaciones o anonimizaciones autorizadas por la Directora."

    def handle(self, *args, **options):
        n = 0
        for r in RetencionEliminacion.objects.filter(estado="autorizada", autorizada_por__isnull=False):
            ejecutar(r)
            n += 1
        self.stdout.write(self.style.SUCCESS("%d expedientes procesados." % n))
