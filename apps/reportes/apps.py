from django.apps import AppConfig


class Config(AppConfig):
    name = "apps.reportes"
    label = "reportes"
    verbose_name = "Reportabilidad"
    default_auto_field = "django.db.models.BigAutoField"
