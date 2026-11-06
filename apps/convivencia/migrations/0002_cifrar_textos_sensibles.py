# Cifra con AES-256-GCM columnas de texto libre con datos sensibles (Ley 21.719). Los valores existentes
# se cifran en su lugar; la migración es reversible.

import apps.core.campos
import apps.core.validadores
from django.db import migrations

from apps.core.migraciones import cifrar_columna


class Migration(migrations.Migration):

    dependencies = [
        ("convivencia", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="anotacion",
            name="descripcion",
            field=apps.core.campos.TextoCifrado(
                editable=True,
                validators=[apps.core.validadores.TextoMinimoValidator(10)],
                verbose_name="descripción",
            ),
        ),
        migrations.AlterField(
            model_name="evidenciaactividad",
            name="nombre_archivo",
            field=apps.core.campos.TextoCifrado(
                editable=True, max_length=160, verbose_name="nombre del archivo"
            ),
        ),
        migrations.AlterField(
            model_name="registroconductual",
            name="descripcion",
            field=apps.core.campos.TextoCifrado(
                editable=True,
                validators=[apps.core.validadores.TextoMinimoValidator(10)],
                verbose_name="descripción",
            ),
        ),
        cifrar_columna("anotacion", "descripcion", "id_anotacion"),
        cifrar_columna("evidencia_actividad", "nombre_archivo", "id_evidencia"),
        cifrar_columna("registro_conductual", "descripcion", "id_registro"),
    ]
