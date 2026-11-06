from django.core.management.base import BaseCommand

from apps.evaluacion.servicios import procesar_reevaluaciones


class Command(BaseCommand):
    help = "Tarea diaria (RF-08): avisa a la Coordinación PIE y al responsable de las reevaluaciones próximas o vencidas."

    def handle(self, *args, **options):
        n = procesar_reevaluaciones()
        self.stdout.write(self.style.SUCCESS("%d avisos de reevaluación creados." % n))
