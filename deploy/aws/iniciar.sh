#!/bin/sh
# Arranque en la EC2 (por Session Manager; sin SSH). Requiere Docker con el complemento compose y la AWS CLI.
# Los secretos de la aplicación se leen de Secrets Manager con el rol de IAM de la instancia.
set -e
cd "$(dirname "$0")"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_SECRETS_ID="${AWS_SECRETS_ID:-stq/produccion}"
: "${IMAGEN:?Defina IMAGEN, por ejemplo <cuenta>.dkr.ecr.us-east-1.amazonaws.com/stq-app:1.1}"
: "${DOMINIO_ORIGEN:?Defina DOMINIO_ORIGEN (nombre del origen en Route 53, por ejemplo origen.<dominio>)}"
: "${CORREO_ACME:?Defina CORREO_ACME (correo para los avisos de Let's Encrypt)}"

# Encabezado secreto que CloudFront agrega al origen (custom origin header «X-Origen-STQ»).
CLAVE_ORIGEN="$(aws secretsmanager get-secret-value --region "$AWS_REGION" --secret-id "$AWS_SECRETS_ID" \
  --query SecretString --output text | python3 -c 'import json,sys; print(json.load(sys.stdin)["CLAVE_ORIGEN"])')"
export CLAVE_ORIGEN IMAGEN DOMINIO_ORIGEN

# Primer certificado (una vez). Las renovaciones las hace el servicio «certificados».
if ! docker compose -f docker-compose.prod.yml run --rm --entrypoint sh certificados \
     -c "test -f /etc/letsencrypt/live/$DOMINIO_ORIGEN/fullchain.pem"; then
  docker compose -f docker-compose.prod.yml run --rm --entrypoint certbot certificados certonly \
    --dns-route53 -d "$DOMINIO_ORIGEN" --email "$CORREO_ACME" --agree-tos --non-interactive
fi

docker compose -f docker-compose.prod.yml pull app proxy certificados
docker compose -f docker-compose.prod.yml up -d
