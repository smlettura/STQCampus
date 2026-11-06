# Imagen de la aplicación (la misma que se ejecuta en EC2 con Docker en AWS).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Certificados de las autoridades de Amazon RDS para validar el TLS hacia la base (DB_SSL_CA).
ADD https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem /app/certs/rds-global-bundle.pem

COPY . .
RUN chmod +x docker/entrypoint.sh \
    && useradd --create-home --uid 10001 bienestar \
    && chmod 644 /app/certs/rds-global-bundle.pem \
    && mkdir -p /app/almacenamiento /app/staticfiles \
    && chown -R bienestar:bienestar /app/almacenamiento /app/staticfiles

USER bienestar
EXPOSE 8000
ENTRYPOINT ["docker/entrypoint.sh"]
