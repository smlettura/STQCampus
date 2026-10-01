from django.apps import AppConfig


class Config(AppConfig):
    name = "apps.ia"
    label = "ia"
    verbose_name = "Copiloto de IA"
    default_auto_field = "django.db.models.BigAutoField"
