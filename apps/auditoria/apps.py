from django.apps import AppConfig


class Config(AppConfig):
    name = "apps.auditoria"
    label = "auditoria"
    verbose_name = "Bitácora de auditoría"
    default_auto_field = "django.db.models.BigAutoField"
