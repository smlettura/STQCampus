from django.core.management.base import BaseCommand

from apps.core.inicializacion import inicializar_sistema


class Command(BaseCommand):
    help = "Crea o actualiza sedes, permisos, roles y las reglas de enrutamiento del reglamento interno (idempotente)."

    def handle(self, *args, **options):
        r = inicializar_sistema()
        self.stdout.write(self.style.SUCCESS(
            "Listo: %(permisos)d permisos, %(roles)d roles, %(sedes)d sedes y %(reglas)d reglas de enrutamiento." % r))
