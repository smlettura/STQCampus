"""Configuración de la Plataforma de Bienestar Psicológico Estudiantil.

Todos los valores sensibles se leen desde variables de entorno (o desde un archivo .env en la raíz del proyecto).
En producción las variables provienen de la configuración de App Service con referencias a Key Vault.
"""
import base64
import hashlib
import os
import sys
import warnings
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _cargar_env(ruta):
    """Lee un archivo .env simple (CLAVE=valor) sin dependencias externas. No sobrescribe variables ya definidas."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


_cargar_env(BASE_DIR / ".env")


def env(clave, defecto=None):
    """Una variable vacía (por ejemplo «ADJUNTOS_DIR=» copiado de .env.example) cuenta como no definida."""
    valor = os.environ.get(clave, "").strip()
    return valor if valor else defecto


def env_bool(clave, defecto=False):
    return str(env(clave, str(defecto))).lower() in ("1", "true", "si", "sí", "yes", "on")


def env_lista(clave, defecto=""):
    return [v.strip() for v in str(env(clave, defecto)).split(",") if v.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)
EN_PRUEBAS = sys.argv[1:2] == ["test"]
SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG or EN_PRUEBAS:
        SECRET_KEY = "solo-desarrollo-cambiar-esta-clave-" + "x" * 20
    else:
        raise ImproperlyConfigured("Defina DJANGO_SECRET_KEY en el entorno.")

ALLOWED_HOSTS = env_lista("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_lista("DJANGO_CSRF_TRUSTED_ORIGINS", "")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.core",
    "apps.cuentas",
    "apps.auditoria",
    "apps.estudiantes",
    "apps.casos",
    "apps.evaluacion",
    "apps.ia",
    "apps.convivencia",
    "apps.cumplimiento",
    "apps.alertas",
    "apps.reportes",
    "apps.api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.ContextoSolicitudMiddleware",
    "apps.cuentas.middleware.SegundoFactorMiddleware",
    "apps.cuentas.middleware.CambioContrasenaMiddleware",
    "apps.core.middleware.CabecerasSeguridadMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.plataforma",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ------------------------------------------------------------------ base de datos
# DB_ENGINE=sqlite (por defecto, para probar rápido) o DB_ENGINE=mysql (MySQL 8, igual que producción).
if env("DB_ENGINE", "sqlite") == "mysql":
    _opciones = {
        "charset": "utf8mb4",
        "init_command": "SET sql_mode='STRICT_TRANS_TABLES', time_zone='+00:00'",
        "isolation_level": "read committed",
    }
    if env("DB_SSL_CA"):
        _opciones["ssl"] = {"ca": env("DB_SSL_CA")}
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": env("DB_NAME", "bienestar"),
            "USER": env("DB_USER", "bienestar_app"),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "127.0.0.1"),
            "PORT": env("DB_PORT", "3306"),
            "OPTIONS": _opciones,
            "CONN_MAX_AGE": 60,
            "TEST": {"CHARSET": "utf8mb4", "COLLATION": "utf8mb4_0900_ai_ci"},
        }
    }
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / env("DB_NAME_SQLITE", "db.sqlite3")}}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "cuentas.Usuario"
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
     "OPTIONS": {"user_attributes": ("correo", "nombre_completo")}},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "apps.cuentas.validadores.ComplejidadContrasenaValidator"},
]

LOGIN_URL = "cuentas:login"
LOGIN_REDIRECT_URL = "core:inicio"
LOGOUT_REDIRECT_URL = "cuentas:login"

# ------------------------------------------------------------------ internacionalización
LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------------ archivos estáticos y adjuntos
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage" if not (DEBUG or EN_PRUEBAS)
                    else "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
# Los adjuntos se guardan cifrados. En producción esta carpeta se reemplaza por el contenedor «adjuntos» de Blob Storage.
ADJUNTOS_DIR = Path(env("ADJUNTOS_DIR", str(BASE_DIR / "almacenamiento" / "adjuntos")))
BITACORA_EXPORT_DIR = Path(env("BITACORA_EXPORT_DIR", str(BASE_DIR / "almacenamiento" / "auditoria-inmutable")))
ADJUNTO_MAX_MB = int(env("ADJUNTO_MAX_MB", "10"))
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024

# ------------------------------------------------------------------ cifrado a nivel de campo (RNF-01)
# CIFRADO_CLAVES: lista "id:clave_base64_32_bytes" separada por comas; la primera es la activa (permite rotación).
# Genere una clave con: python manage.py generar_clave_cifrado
_claves = env_lista("CIFRADO_CLAVES", "")
CIFRADO_CLAVES = {}
for _item in _claves:
    _id, _, _clave = _item.partition(":")
    CIFRADO_CLAVES[_id] = base64.urlsafe_b64decode(_clave)
if not CIFRADO_CLAVES:
    if DEBUG or EN_PRUEBAS:
        warnings.warn("CIFRADO_CLAVES no definida: se usa una clave derivada de SECRET_KEY (solo desarrollo).")
        CIFRADO_CLAVES = {"dev": hashlib.sha256(("cifrado:" + SECRET_KEY).encode()).digest()}
    else:
        raise ImproperlyConfigured("Defina CIFRADO_CLAVES en el entorno (clave de Key Vault).")
CIFRADO_CLAVE_ACTIVA = next(iter(CIFRADO_CLAVES))
for _id, _k in CIFRADO_CLAVES.items():
    if len(_k) != 32:
        raise ImproperlyConfigured("La clave de cifrado '%s' debe tener 32 bytes (AES-256)." % _id)

# ------------------------------------------------------------------ sesión y seguridad
SESSION_COOKIE_AGE = int(env("SESION_MINUTOS", "30")) * 60
SESSION_SAVE_EVERY_REQUEST = True            # la sesión expira tras 30 minutos de inactividad
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
if not DEBUG and not EN_PRUEBAS:
    # HTTPS_OBLIGATORIO=0 solo para probar localmente sin TLS (por ejemplo, docker compose en el propio equipo).
    HTTPS_OBLIGATORIO = env_bool("HTTPS_OBLIGATORIO", True)
    SECURE_SSL_REDIRECT = HTTPS_OBLIGATORIO
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = HTTPS_OBLIGATORIO
    SECURE_HSTS_SECONDS = 31536000 if HTTPS_OBLIGATORIO else 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = HTTPS_OBLIGATORIO

# Roles que deben usar segundo factor: perfiles clínicos, Directora y administrador (RNF-01, RNF-02).
ROLES_CON_2FA = ["psicologa", "asistente_social", "encargada_convivencia", "coordinacion_pie", "directora",
                 "administrador", "psicologa_denunciante"]
LOGIN_MAX_INTENTOS = int(env("LOGIN_MAX_INTENTOS", "5"))
LOGIN_BLOQUEO_MINUTOS = int(env("LOGIN_BLOQUEO_MINUTOS", "15"))
PASSWORD_RESET_TIMEOUT = 60 * 60           # el enlace para restablecer la contraseña vale 1 hora
RECORDAR_CORREO_DIAS = 30                  # «Recordarme» guarda solo el correo, nunca la contraseña ni la sesión

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "bienestar"}}

# ------------------------------------------------------------------ correo
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Plataforma de Bienestar <no-responder@colegio.cl>")
URL_PLATAFORMA = env("URL_PLATAFORMA", "http://localhost:8000")

# ------------------------------------------------------------------ reglas del negocio
RETENCION_ANIOS = 15                     # RNF-10: plazo de conservación (decisión de la usuaria, E20)
REEVALUACION_ANIOS_TRANSITORIA = 2       # RF-08: reevaluación bianual de NEE transitorias
AVISO_REEVALUACION_DIAS = int(env("AVISO_REEVALUACION_DIAS", "60"))
PLAZO_DENUNCIA_HORAS = 24                # Código Procesal Penal, arts. 175 y 176
ARCO_PLAZO_DIAS = int(env("ARCO_PLAZO_DIAS", "30"))   # ajustar al plazo legal vigente
TAREAS_TOKEN = env("TAREAS_TOKEN", "")    # token que envía Azure Functions al invocar las tareas programadas

# ------------------------------------------------------------------ módulo de IA
# Espacio reservado: el modelo está en entrenamiento y la plataforma aún no genera contenido (ver apps/ia/servicios.py).

# ------------------------------------------------------------------ API REST
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.UserRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"user": "120/min"},
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"consola": {"class": "logging.StreamHandler"}},
    "loggers": {"bienestar": {"handlers": ["consola"], "level": env("LOG_LEVEL", "INFO")}},
}

NOMBRE_PLATAFORMA = "Plataforma de Bienestar Psicológico Estudiantil"
NOMBRE_MARCA = env("NOMBRE_MARCA", "STQCampus")   # marca visible del diseño «panel analítico»
NOMBRE_COLEGIO = "Colegio Santa Teresa de Quilpué"
