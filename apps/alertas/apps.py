from django.apps import AppConfig


class Config(AppConfig):
    name = "apps.alertas"
    label = "alertas"
    verbose_name = "Alertas de riesgo"
    default_auto_field = "django.db.models.BigAutoField"
