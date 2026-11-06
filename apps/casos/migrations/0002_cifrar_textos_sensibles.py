# Cifra con AES-256-GCM columnas de texto libre con datos sensibles (Ley 21.719). Los valores existentes
# se cifran en su lugar; la migración es reversible.

import apps.core.campos
import apps.core.validadores
from django.db import migrations

from apps.core.migraciones import cifrar_columna


class Migration(migrations.Migration):

    dependencies = [
        ("casos", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="documento",
            name="nombre_archivo",
            field=apps.core.campos.TextoCifrado(
                editable=True, max_length=160, verbose_name="nombre del archivo"
            ),
        ),
        migrations.AlterField(
            model_name="hito",
            name="descripcion",
            field=apps.core.campos.TextoCifrado(
                editable=True,
                validators=[apps.core.validadores.TextoMinimoValidator(5)],
                verbose_name="descripción",
            ),
        ),
        cifrar_columna("documento", "nombre_archivo", "id_documento"),
        cifrar_columna("hito", "descripcion", "id_hito"),
    ]
