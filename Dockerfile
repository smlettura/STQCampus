# Imagen de la aplicación (misma que se publicaría en Azure App Service para contenedores).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN chmod +x docker/entrypoint.sh \
    && useradd --create-home --uid 10001 bienestar \
    && mkdir -p /app/almacenamiento /app/staticfiles \
    && chown -R bienestar:bienestar /app/almacenamiento /app/staticfiles

USER bienestar
EXPOSE 8000
ENTRYPOINT ["docker/entrypoint.sh"]
