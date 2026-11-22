"""Revisiones de despliegue propias (se muestran con «python manage.py check --deploy»)."""
from django.conf import settings
from django.core.checks import Tags, Warning, register


@register(Tags.security, deploy=True)
def revisar_origenes_https(app_configs, **kwargs):
    """Detrás de CloudFront el navegador envía Origin con el dominio público: debe estar en CSRF_TRUSTED_ORIGINS."""
    avisos = []
    origenes = list(getattr(settings, "CSRF_TRUSTED_ORIGINS", []))
    if not origenes:
        avisos.append(Warning("CSRF_TRUSTED_ORIGINS está vacío.",
                              hint="Defina DJANGO_CSRF_TRUSTED_ORIGINS=https://<dominio público de CloudFront>.",
                              id="stq.W001"))
    elif any(not o.startswith("https://") for o in origenes):
        avisos.append(Warning("CSRF_TRUSTED_ORIGINS contiene orígenes sin https.", id="stq.W002"))
    if "*" in settings.ALLOWED_HOSTS:
        avisos.append(Warning("ALLOWED_HOSTS acepta cualquier nombre ('*').",
                              hint="Liste el dominio público y el del origen (DOMINIO_ORIGEN).", id="stq.W003"))
    return avisos
