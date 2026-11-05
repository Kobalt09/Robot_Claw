#!/usr/bin/env bash
set -e

# Cargar entorno de ROS 2
if [ -n "$ROS_DISTRO" ] && [ -f "/opt/ros/$ROS_DISTRO/setup.bash" ]; then
    source "/opt/ros/$ROS_DISTRO/setup.bash"
fi

# Compilar interfaces en un directorio interno del contenedor para NO contaminar el disco de Windows con symlinks
BUILD_DIR="/opt/bridge_build"
INSTALL_DIR="/opt/bridge_install"
LOG_DIR="/opt/bridge_log"

if [ -d "/ws/src/multirobot_interfaces" ]; then
    cd /ws
    colcon --log-base "$LOG_DIR" build \
        --packages-select multirobot_interfaces \
        --build-base "$BUILD_DIR" \
        --install-base "$INSTALL_DIR"
    
    if [ -f "$INSTALL_DIR/setup.bash" ]; then
        source "$INSTALL_DIR/setup.bash"
    fi
fi

echo "[ROS 2 Bridge] Interfaces multirobot_interfaces compiladas y cargadas desde $INSTALL_DIR."
echo "[ROS 2 Bridge] Iniciando puente hacia Perry en ${PERRY_API:-http://172.25.32.1:8000}..."

exec python3 -u /ws/perry/perry_ros_bridge.py
