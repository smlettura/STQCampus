from django.apps import AppConfig


class Config(AppConfig):
    name = "apps.evaluacion"
    label = "evaluacion"
    verbose_name = "Evaluación diagnóstica y PIE"
    default_auto_field = "django.db.models.BigAutoField"
