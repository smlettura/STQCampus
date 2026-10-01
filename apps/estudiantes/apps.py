from django.apps import AppConfig


class Config(AppConfig):
    name = "apps.estudiantes"
    label = "estudiantes"
    verbose_name = "Estudiantes y apoderados"
    default_auto_field = "django.db.models.BigAutoField"
