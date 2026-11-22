#!/bin/sh
# Comprobaciones después del despliegue. Ejecutar desde cualquier equipo con curl:
#   PUBLICO=plataforma.<dominio> ORIGEN=origen.<dominio> sh verificar_despliegue.sh
set -u
: "${PUBLICO:?Defina PUBLICO (dominio de CloudFront)}"; : "${ORIGEN:?Defina ORIGEN (nombre del origen)}"
ok=0; falla=0
revisar() { if [ "$2" = "$3" ]; then echo "  OK    $1 ($2)"; ok=$((ok+1)); else echo "  FALLA $1: se esperaba $3 y se obtuvo $2"; falla=$((falla+1)); fi; }
echo "Plataforma pública (CloudFront):"
revisar "acceso por HTTPS" "$(curl -s -o /dev/null -w '%{http_code}' "https://$PUBLICO/cuentas/login/")" 200
revisar "HTTP redirige a HTTPS" "$(curl -s -o /dev/null -w '%{http_code}' "http://$PUBLICO/cuentas/login/")" 301
cab="$(curl -s -D - -o /dev/null "https://$PUBLICO/cuentas/login/")"
revisar "pasa por CloudFront" "$(echo "$cab" | grep -ci '^x-cache:')" 1
revisar "HSTS activo" "$(echo "$cab" | grep -ci '^strict-transport-security:')" 1
revisar "cookie CSRF con Secure" "$(echo "$cab" | grep -i '^set-cookie: csrftoken' | grep -ci 'secure')" 1
echo "Origen (debe estar cerrado para todos menos CloudFront):"
directo="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$ORIGEN/" || true)"
case "$directo" in 000|403) revisar "acceso directo al origen bloqueado" bloqueado bloqueado;; *) revisar "acceso directo al origen bloqueado" "$directo" "000 o 403";; esac
echo "Certificado del origen:"
emisor="$(echo | openssl s_client -connect "$ORIGEN:443" -servername "$ORIGEN" 2>/dev/null | openssl x509 -noout -issuer 2>/dev/null || true)"
echo "  (si el grupo de seguridad bloquea este equipo, revíselo desde la EC2) ${emisor:-sin respuesta}"
echo "Resultado: $ok correctas, $falla con problemas."
[ "$falla" -eq 0 ]
