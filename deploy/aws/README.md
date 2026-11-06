# Despliegue en AWS (piloto)

Arquitectura: región sa-east-1 · Application Load Balancer con certificado ACM · EC2 (t3.small) con Docker en subred
privada · Amazon RDS for MySQL 8.4 · S3 (adjuntos con SSE-KMS y bitácora con Object Lock) · Secrets Manager y KMS ·
CloudWatch · EventBridge Scheduler + Systems Manager. El modelo de IA (Gemma 2 9B con Ollama) corre fuera de AWS, en un
equipo propio que consulta la cola de la plataforma por HTTPS con un token; no se abren puertos hacia ese equipo.

1. Crear el secreto JSON `stq/produccion` en Secrets Manager con: DJANGO_SECRET_KEY, CIFRADO_CLAVES, DB_HOST, DB_NAME,
   DB_USER, DB_PASSWORD, DB_MIGRA_USER, DB_MIGRA_PASSWORD, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, DJANGO_ALLOWED_HOSTS,
   DJANGO_CSRF_TRUSTED_ORIGINS, URL_PLATAFORMA, AWS_KMS_KEY_ID.
2. Asignar a la instancia el rol de IAM con la política `iam_politica_instancia.json`.
3. Publicar la imagen en Amazon ECR y ejecutar `iniciar.sh` en la instancia (por Session Manager; sin SSH).
4. Crear las tareas programadas con `programar_tareas.sh`.
