#!/usr/bin/env bash
set -e

# Source entorno base de ROS 2 si existe
if [ -n "$ROS_DISTRO" ] && [ -f "/opt/ros/$ROS_DISTRO/setup.bash" ]; then
    source "/opt/ros/$ROS_DISTRO/setup.bash"
fi

# Compilar interfaces locales si existen en /ws/src
if [ -d "/ws/src/multirobot_interfaces" ]; then
    cd /ws
    colcon build --symlink-install || true
    if [ -f "/ws/install/setup.bash" ]; then
        source "/ws/install/setup.bash"
    fi
fi

cd /ws/perry

# Si se pasan argumentos, ejecutarlos; de lo contrario arrancar audit_web.py
if [ $# -gt 0 ]; then
    exec "$@"
else
    exec python3 audit_web.py
fi
