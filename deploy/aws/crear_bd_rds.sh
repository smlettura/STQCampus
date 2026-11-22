#!/bin/sh
# Crea la base «bienestar» y los usuarios bienestar_migra y bienestar_app en Amazon RDS (una sola vez).
# Las contraseñas de esos usuarios se leen del secreto (DB_MIGRA_PASSWORD y DB_PASSWORD); la del usuario maestro de
# RDS se pide por teclado y no se guarda. Ejecutar en la EC2 desde la raíz del repositorio:
#   RDS_HOST=<endpoint de RDS> RDS_MAESTRO=admin sh deploy/aws/crear_bd_rds.sh
set -e
export AWS_REGION="${AWS_REGION:-us-east-1}"
SECRETO="${AWS_SECRETS_ID:-stq/produccion}"
: "${RDS_HOST:?Defina RDS_HOST (endpoint de la instancia RDS)}"
RDS_MAESTRO="${RDS_MAESTRO:-admin}"
valor() {
  aws secretsmanager get-secret-value --region "$AWS_REGION" --secret-id "$SECRETO" --query SecretString --output text \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['$1'])"
}
MIGRA="$(valor DB_MIGRA_PASSWORD)"; APP="$(valor DB_PASSWORD)"
case "$MIGRA$APP" in *"'"*|*\\*|*/*|*"&"*) echo "Las contraseñas no deben contener comillas simples, barras ni el signo &." >&2; exit 1;; esac
# Mismo script que en local, sin la línea de la base de pruebas y con las contraseñas del secreto.
SQL="$(grep -v 'test_bienestar' sql/00_crear_bd_y_usuarios.sql \
  | sed "s/Cambiar_Migra_2026/$MIGRA/; s/Cambiar_App_2026/$APP/")"
printf "Contraseña del usuario maestro de RDS (%s): " "$RDS_MAESTRO"; stty -echo; read -r MAESTRA; stty echo; echo
printf '%s\n' "$SQL" | docker run --rm -i -e MYSQL_PWD="$MAESTRA" mysql:8.4 \
  mysql --ssl-mode=REQUIRED -h "$RDS_HOST" -u "$RDS_MAESTRO"
echo "Base y usuarios creados. Siguiente paso: deploy/aws/iniciar.sh"
