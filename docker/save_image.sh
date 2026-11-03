#!/usr/bin/env bash
# Construye en la PC la imagen de Perry para la Pi (arm64, emulado) y la guarda en un archivo,
# para llevarla por el cable a una Pi sin internet (docker/deploy_pi.sh).
#   bash docker/save_image.sh
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=docker/perry_claw_lyrical_arm64.tar.gz

docker buildx build --platform linux/arm64 --build-arg BASE_IMAGE=ros:lyrical-ros-base \
    -t perry_claw:lyrical -f docker/Dockerfile --load .
docker save perry_claw:lyrical | gzip > "$OUT"
echo "Imagen guardada en $OUT ($(du -h "$OUT" | cut -f1))"
