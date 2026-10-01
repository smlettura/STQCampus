from django.apps import AppConfig


class Config(AppConfig):
    name = "apps.cuentas"
    label = "cuentas"
    verbose_name = "Cuentas, roles y segundo factor"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import senales  # noqa: F401

