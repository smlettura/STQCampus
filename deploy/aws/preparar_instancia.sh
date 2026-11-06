#!/bin/sh
# Prepara una EC2 t4g.small con Amazon Linux 2023 (ARM). Ejecutar una vez, como root, por Session Manager:
#   sudo sh preparar_instancia.sh
# Instala Docker, el complemento compose y git. La AWS CLI, python3 y el agente de Systems Manager ya vienen en AL2023.
set -e
if [ "$(uname -m)" != "aarch64" ]; then echo "Se esperaba una instancia ARM (t4g); esta es $(uname -m)." >&2; fi
dnf install -y docker git
systemctl enable --now docker
VERSION_COMPOSE="v2.29.7"
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL "https://github.com/docker/compose/releases/download/${VERSION_COMPOSE}/docker-compose-linux-$(uname -m)" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
# Swap de 1 GiB: margen para la construcción de la imagen y picos de memoria en una instancia de 2 GiB.
if [ ! -f /swapfile ]; then
  dd if=/dev/zero of=/swapfile bs=1M count=1024 && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo "/swapfile swap swap defaults 0 0" >> /etc/fstab
fi
docker --version && docker compose version
echo "Instancia lista. Siguiente paso: clonar el repositorio y ejecutar deploy/aws/crear_bd_rds.sh"
