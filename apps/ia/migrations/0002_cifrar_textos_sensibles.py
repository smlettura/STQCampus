# Cifra con AES-256-GCM columnas de texto libre con datos sensibles (Ley 21.719). Los valores existentes
# se cifran en su lugar; la migración es reversible.

import apps.core.campos
import apps.core.validadores
from django.db import migrations

from apps.core.migraciones import cifrar_columna


class Migration(migrations.Migration):

    dependencies = [
        ("ia", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="retroalimentacionia",
            name="comentario",
            field=apps.core.campos.TextoCifrado(
                editable=True,
                validators=[apps.core.validadores.TextoMinimoValidator(10)],
                verbose_name="comentario",
            ),
        ),
        cifrar_columna("retroalimentacion_ia", "comentario", "id_retro"),
    ]
