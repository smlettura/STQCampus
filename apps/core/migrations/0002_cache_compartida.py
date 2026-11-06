"""Crea la tabla de la caché compartida (DatabaseCache) para que la usen todos los trabajadores de Gunicorn."""
from django.core.management import call_command
from django.db import migrations


def crear_tabla(apps, schema_editor):
    call_command("createcachetable", database=schema_editor.connection.alias, verbosity=0)


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [migrations.RunPython(crear_tabla, migrations.RunPython.noop)]
