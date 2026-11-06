from django.apps import AppConfig


class Config(AppConfig):
    name = "apps.core"
    label = "core"
    verbose_name = "Núcleo"
    default_auto_field = "django.db.models.BigAutoField"
