from django.apps import AppConfig


class Config(AppConfig):
    name = "apps.casos"
    label = "casos"
    verbose_name = "Gestión de casos"
    default_auto_field = "django.db.models.BigAutoField"
