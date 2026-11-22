#!/bin/sh
# Arranque en la EC2 (por Session Manager; sin SSH). Ejecutar desde la raíz del repositorio:
#   DOMINIO_ORIGEN=origen.<dominio> CORREO_ACME=<correo> sh deploy/aws/iniciar.sh
# Sin CloudFront (AWS Academy Learner Lab no permite crear distribuciones): el dominio es el público y nginx atiende
# directo a los navegadores:
#   SIN_CLOUDFRONT=1 DOMINIO_ORIGEN=app.<dominio> CORREO_ACME=<correo> sh deploy/aws/iniciar.sh
# Por defecto construye la imagen en la propia instancia (es ARM, igual que la producción). Para usar una imagen ya
# publicada en Amazon ECR, defina IMAGEN=<cuenta>.dkr.ecr.us-east-1.amazonaws.com/stq-app:<versión>.
# Los secretos de la aplicación se leen de Secrets Manager con el rol de IAM de la instancia.
set -e
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$RAIZ/deploy/aws"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_SECRETS_ID="${AWS_SECRETS_ID:-stq/produccion}"
: "${DOMINIO_ORIGEN:?Defina DOMINIO_ORIGEN (nombre del origen en Route 53, por ejemplo origen.<dominio>)}"
: "${CORREO_ACME:?Defina CORREO_ACME (correo para los avisos de vencimiento del certificado)}"
COMPOSE="docker compose -f docker-compose.prod.yml"

if [ -z "${IMAGEN:-}" ]; then
  IMAGEN="stq-app:$(git -C "$RAIZ" rev-parse --short HEAD 2>/dev/null || echo local)"
  echo "Construyendo la imagen $IMAGEN en esta instancia..."
  docker build -t "$IMAGEN" "$RAIZ"
  DESCARGAR="proxy certificados"
else
  DESCARGAR="app proxy certificados"
fi

# Encabezado secreto que CloudFront agrega al origen (custom origin header «X-Origen-STQ»).
CLAVE_ORIGEN="$(aws secretsmanager get-secret-value --region "$AWS_REGION" --secret-id "$AWS_SECRETS_ID" \
  --query SecretString --output text | python3 -c 'import json,sys; print(json.load(sys.stdin)["CLAVE_ORIGEN"])')"
export CLAVE_ORIGEN IMAGEN DOMINIO_ORIGEN
if [ "${SIN_CLOUDFRONT:-0}" = "1" ]; then
  export PLANTILLA_PROXY=./proxy/stq-directo.conf.template
  echo "Modo sin CloudFront: nginx atiende directo en https://$DOMINIO_ORIGEN"
fi

$COMPOSE pull $DESCARGAR
# Primer certificado (una vez). Las renovaciones las hace el servicio «certificados».
if ! $COMPOSE run --rm --entrypoint sh certificados -c "test -f /etc/letsencrypt/live/$DOMINIO_ORIGEN/fullchain.pem"; then
  $COMPOSE run --rm --entrypoint certbot certificados certonly \
    --dns-route53 -d "$DOMINIO_ORIGEN" --email "$CORREO_ACME" --agree-tos --non-interactive
fi
$COMPOSE up -d
echo "Servicios iniciados. Revise con: docker compose -f deploy/aws/docker-compose.prod.yml ps"
echo "Siguiente paso: crear la cuenta de administrador y ejecutar deploy/aws/verificar_despliegue.sh"
