#!/usr/bin/env bash
# Copia el código a la Pi de Perry por SSH, carga la imagen si hace falta y levanta el contenedor.
# Funciona sin internet en la Pi (con la imagen guardada por docker/save_image.sh).
#   bash docker/deploy_pi.sh                       # Pi en el cable directo (169.254.49.182)
#   PI=manipulador@<otra-ip> bash docker/deploy_pi.sh
#   BUILD=1 bash docker/deploy_pi.sh               # la Pi tiene internet: construye ahí mismo
set -euo pipefail
cd "$(dirname "$0")/.."
PI=${PI:-manipulador@169.254.49.182}
DIR=Robot_Claw_perry
IMG=docker/perry_claw_lyrical_arm64.tar.gz

echo "== 1. Código (último commit) -> $PI:~/$DIR"
git archive HEAD | ssh "$PI" "mkdir -p ~/$DIR && tar -xmf - -C ~/$DIR"

echo "== 2. Panel nativo: se detiene (el contenedor usa el puerto 8000, la Maestro y la cámara)"
ssh "$PI" 'pkill -f "^python3 audit_web.py" || true'

if [ "${BUILD:-0}" = "1" ]; then
    echo "== 3. Construyendo la imagen en la Pi (necesita internet)"
    ssh "$PI" "cd ~/$DIR && docker compose build"
elif ssh "$PI" 'docker image inspect perry_claw:lyrical >/dev/null 2>&1'; then
    echo "== 3. La imagen perry_claw:lyrical ya está en la Pi"
else
    [ -f "$IMG" ] || { echo "Falta $IMG: correr antes bash docker/save_image.sh"; exit 1; }
    echo "== 3. Cargando la imagen en la Pi ($(du -h "$IMG" | cut -f1), por el cable)"
    ssh "$PI" 'gunzip | docker load' < "$IMG"
fi

echo "== 4. Levantando el contenedor"
ssh "$PI" "cd ~/$DIR && docker compose up -d --no-build && sleep 15 && docker compose logs --tail 30"
echo "Panel: http://${PI#*@}:8000"
