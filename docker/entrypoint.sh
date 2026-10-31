#!/usr/bin/env bash
set -e

# Source entorno base de ROS 2 si existe
if [ -n "$ROS_DISTRO" ] && [ -f "/opt/ros/$ROS_DISTRO/setup.bash" ]; then
    source "/opt/ros/$ROS_DISTRO/setup.bash"
fi

# Compilar interfaces locales si existen en /ws/src
if [ -d "/ws/src/multirobot_interfaces" ]; then
    cd /ws
    if [ "${PERRY_CLEAN_BUILD:-0}" = "1" ]; then
        echo "[entrypoint] PERRY_CLEAN_BUILD=1: limpiando build/, install/ y log/..."
        rm -rf /ws/build /ws/install /ws/log
    fi
    echo "[entrypoint] Compilando multirobot_interfaces..."
    colcon build --symlink-install --packages-select multirobot_interfaces || true
    if [ -f "/ws/install/setup.bash" ]; then
        source "/ws/install/setup.bash"
        echo "[entrypoint] Interfaces multirobot_interfaces compiladas y cargadas."
    else
        echo "[entrypoint] ADVERTENCIA: /ws/install/setup.bash no encontrado tras compilacion."
    fi
fi

cd /ws/perry

# Si se pasan argumentos, ejecutarlos; de lo contrario arrancar audit_web.py
if [ $# -gt 0 ]; then
    exec "$@"
else
    exec python3 audit_web.py
fi
