#!/bin/sh
# Arranque del contenedor: espera a MySQL, migra con el usuario propietario, otorga permisos mínimos al usuario de la
# aplicación (sin UPDATE/DELETE sobre la bitácora), inicializa roles y reglas, y levanta gunicorn.
set -e

if [ "$DB_ENGINE" = "mysql" ]; then
  echo "Esperando a MySQL en $DB_HOST:${DB_PORT:-3306}..."
  python - <<'PY'
import os, sys, time
import pymysql
for intento in range(60):
    try:
        pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ.get("DB_PORT", "3306")),
                        user=os.environ["DB_MIGRA_USER"], password=os.environ["DB_MIGRA_PASSWORD"],
                        database=os.environ.get("DB_NAME", "bienestar")).close()
        sys.exit(0)
    except Exception:
        time.sleep(2)
sys.exit("MySQL no respondió a tiempo.")
PY
  echo "Migrando con el usuario propietario del esquema..."
  DB_USER="$DB_MIGRA_USER" DB_PASSWORD="$DB_MIGRA_PASSWORD" python manage.py migrate --noinput
  DB_USER="$DB_MIGRA_USER" DB_PASSWORD="$DB_MIGRA_PASSWORD" python manage.py permisos_bd --aplicar --usuario "$DB_USER"
else
  python manage.py migrate --noinput
fi

python manage.py inicializar_sistema

if [ "$CARGAR_DATOS_DEMO" = "1" ]; then
  python manage.py cargar_datos_demo || echo "Datos de demostración ya cargados; se omiten."
fi

python manage.py collectstatic --noinput

# t4g.small (2 vCPU, 2 GiB): 3 trabajadores (medidos en local en unos 77 MB cada uno en reposo). Se reciclan cada
# 1000 solicitudes para acotar el crecimiento de memoria. --forwarded-allow-ips="*" es seguro porque el puerto 8000
# no se publica: solo lo alcanza el proxy nginx por la red interna de Docker.
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers "${GUNICORN_WORKERS:-3}" \
  --max-requests 1000 --max-requests-jitter 100 --worker-tmp-dir /dev/shm --timeout 60 \
  --access-logfile - --forwarded-allow-ips="*"
