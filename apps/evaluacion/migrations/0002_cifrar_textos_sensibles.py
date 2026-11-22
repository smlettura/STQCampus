# Cifra con AES-256-GCM columnas de texto libre con datos sensibles (Ley 21.719). Los valores existentes
# se cifran en su lugar; la migración es reversible.

import apps.core.campos
from django.db import migrations

from apps.core.migraciones import cifrar_columna


class Migration(migrations.Migration):

    dependencies = [
        ("evaluacion", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="evaluaciondiagnostica",
            name="tipo_nee",
            field=apps.core.campos.TextoCifrado(
                editable=True, max_length=80, verbose_name="tipo de NEE"
            ),
        ),
        migrations.AlterField(
            model_name="planapoyo",
            name="adecuaciones",
            field=apps.core.campos.TextoCifrado(
                editable=True,
                help_text="Visible para el profesor jefe. No incluya información clínica.",
                verbose_name="adecuaciones para el aula",
            ),
        ),
        cifrar_columna("evaluacion_diagnostica", "tipo_nee", "id_evaluacion"),
        cifrar_columna("plan_apoyo", "adecuaciones", "id_plan"),
    ]
