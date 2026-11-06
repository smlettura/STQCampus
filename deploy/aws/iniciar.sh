#!/bin/sh
# Arranque del contenedor en EC2. Los secretos se leen de Secrets Manager con el rol de IAM de la instancia.
set -e
IMAGEN="${IMAGEN:?Defina IMAGEN, por ejemplo <cuenta>.dkr.ecr.sa-east-1.amazonaws.com/stq-app:1.0}"
docker rm -f stq-app 2>/dev/null || true
docker run -d --name stq-app --restart unless-stopped -p 8000:8000 \
  -e DJANGO_DEBUG=0 -e AWS_REGION=sa-east-1 -e AWS_SECRETS_ID=stq/produccion \
  -e DB_ENGINE=mysql -e DB_SSL_CA=/app/certs/rds-global-bundle.pem \
  -e ALMACENAMIENTO=s3 -e AWS_S3_ADJUNTOS=stq-adjuntos -e AWS_S3_BITACORA=stq-bitacora-inmutable \
  --log-driver awslogs --log-opt awslogs-region=sa-east-1 --log-opt awslogs-group=/stq/app \
  "$IMAGEN"
