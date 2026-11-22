import json

from django.core.management.base import BaseCommand

from apps.auditoria.servicios import registrar
from apps.core.tareas import TAREAS


class Command(BaseCommand):
    help = ("Ejecuta la tarea diaria (avisos de reevaluación y copia de la bitácora) o la mensual (retención). "
            "En AWS la invoca EventBridge Scheduler mediante Systems Manager Run Command.")

    def add_arguments(self, parser):
        parser.add_argument("nombre", choices=sorted(TAREAS))

    def handle(self, *args, nombre, **opciones):
        resultado = TAREAS[nombre]()
        registrar(None, "modificacion", "tarea_programada", None, detalle=nombre)
        self.stdout.write(json.dumps(resultado, ensure_ascii=False, default=str))
