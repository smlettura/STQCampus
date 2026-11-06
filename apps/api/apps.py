from django.apps import AppConfig


class Config(AppConfig):
    name = "apps.api"
    label = "api"
    verbose_name = "API REST"
    default_auto_field = "django.db.models.BigAutoField"
