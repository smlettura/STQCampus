import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.auditoria.servicios import exportar_dia


class Command(BaseCommand):
    help = "Exporta los eventos de un día (por defecto, ayer) a un archivo JSON Lines de solo lectura."

    def add_arguments(self, parser):
        parser.add_argument("--fecha", help="AAAA-MM-DD")

    def handle(self, *args, **o):
        fecha = datetime.date.fromisoformat(o["fecha"]) if o.get("fecha") else timezone.localdate() - datetime.timedelta(days=1)
        ruta, n = exportar_dia(fecha)
        self.stdout.write(self.style.SUCCESS("%d eventos exportados a %s" % (n, ruta)))
