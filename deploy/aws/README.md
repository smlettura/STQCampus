# Despliegue en AWS (piloto)

Arquitectura mínima en la región **us-east-1** (Norte de Virginia): Amazon CloudFront con certificado de ACM ·
EC2 **t4g.small** (ARM, 2 vCPU, 2 GiB) con Docker en una subred pública · proxy nginx con TLS en la instancia ·
Amazon RDS for MySQL 8.4 **db.t4g.micro** en una subred privada · S3 (adjuntos con SSE-KMS y bitácora con Object Lock) ·
Secrets Manager y KMS · CloudWatch · EventBridge Scheduler + Systems Manager · Route 53. Sin balanceador ni NAT Gateway:
la instancia tiene IPv4 pública y envía el correo directamente por SMTP 587. El modelo de IA (Gemma 2 9B con Ollama)
corre fuera de AWS, en un equipo propio que consulta la cola de la plataforma por HTTPS con un token.

```
Navegador ──HTTPS (ACM)──▶ CloudFront ──HTTPS (TLS 1.2, Let's Encrypt)──▶ nginx :443 ──HTTP interno──▶ Gunicorn :8000
                                                       grupo de seguridad: solo CloudFront          (red de Docker)
```

## Requisito: un dominio en Route 53

CloudFront valida el certificado del origen contra una autoridad pública y contra el nombre del origen, y **no acepta
certificados autofirmados** (responde 502). Por eso el origen necesita un nombre propio, por ejemplo
`origen.<dominio>`, con un registro A hacia la IPv4 de la instancia, y un certificado de Let's Encrypt que se obtiene
con el desafío DNS-01 en Route 53 (no hace falta abrir el puerto 80). Sin dominio no se puede cumplir el tramo
cifrado CloudFront → origen que exigen las Tablas 55 y 56 del informe.

CloudFront negocia con el origen como máximo **TLSv1.2** (valores admitidos: SSLv3, TLSv1, TLSv1.1, TLSv1.2).

## Pasos

La guía completa, con capturas de los valores de cada pantalla, está en «Guia_Despliegue_AWS_us-east-1.docx».
Resumen:

1. Crear el secreto JSON `stq/produccion` en Secrets Manager con: DJANGO_SECRET_KEY, CIFRADO_CLAVES, DB_HOST, DB_NAME,
   DB_USER, DB_PASSWORD, DB_MIGRA_USER, DB_MIGRA_PASSWORD, EMAIL_BACKEND, EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER,
   EMAIL_HOST_PASSWORD, EMAIL_USE_TLS, DEFAULT_FROM_EMAIL, DJANGO_ALLOWED_HOSTS (`plataforma.<dominio>,origen.<dominio>`),
   DJANGO_CSRF_TRUSTED_ORIGINS (`https://plataforma.<dominio>`), URL_PLATAFORMA, AWS_KMS_KEY_ID y CLAVE_ORIGEN.
2. Asignar a la instancia el rol de IAM con `iam_politica_instancia.json` (reemplace `<cuenta>`, `<arn-llave-kms>`
   e `<id-zona>`). En los metadatos de la instancia, IMDSv2 con límite de saltos 2 (los contenedores lo necesitan).
3. Grupo de seguridad de la instancia: entrada 443 solo desde la lista de prefijos administrada
   `com.amazonaws.global.cloudfront.origin-facing`; sin 22, 80 ni 8000.
4. En la instancia (por Session Manager): `sudo sh deploy/aws/preparar_instancia.sh` (Docker, compose, git y swap).
5. Crear la base y los usuarios en RDS: `RDS_HOST=<endpoint> sh deploy/aws/crear_bd_rds.sh`.
6. Levantar los servicios: `DOMINIO_ORIGEN=origen.<dominio> CORREO_ACME=<correo> sh deploy/aws/iniciar.sh`
   (construye la imagen en la propia instancia ARM; con `IMAGEN=…` usa una imagen publicada en ECR).
7. Crear la cuenta de administrador: `docker exec -it stq-app python manage.py createsuperuser`.
8. CloudFront: origen `origen.<dominio>`, protocolo «solo HTTPS», TLSv1.2, encabezado personalizado `X-Origen-STQ`
   con el valor de CLAVE_ORIGEN; comportamiento con «Redirigir HTTP a HTTPS», métodos GET a DELETE, política de caché
   CachingDisabled y política de solicitud al origen AllViewerExceptHostHeader; certificado de ACM para
   `plataforma.<dominio>` (en us-east-1).
9. Crear las tareas programadas con `programar_tareas.sh`.
10. Comprobar: `PUBLICO=plataforma.<dominio> ORIGEN=origen.<dominio> sh deploy/aws/verificar_despliegue.sh`.
