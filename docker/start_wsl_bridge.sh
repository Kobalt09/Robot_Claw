#!/usr/bin/env bash
set -e

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
export NO_PROXY="localhost,127.0.0.1,10.253.102.98,10.253.102.198"
export no_proxy="$NO_PROXY"

source /opt/ros/jazzy/setup.bash
if [ -f "/opt/bridge_install/setup.bash" ]; then
    source /opt/bridge_install/setup.bash
fi

export ROS_DOMAIN_ID=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_STATIC_PEERS="${ROS_STATIC_PEERS:-10.253.102.198}"
export PERRY_API="${PERRY_API:-http://127.0.0.1:8000}"

echo "=================================================="
echo "[Perry WSL2 Mirrored] IP local: $(hostname -I)"
echo "[Perry WSL2 Mirrored] ROS_DOMAIN_ID=$ROS_DOMAIN_ID"
echo "[Perry WSL2 Mirrored] RMW_IMPLEMENTATION=$RMW_IMPLEMENTATION"
echo "[Perry WSL2 Mirrored] ROS_STATIC_PEERS=$ROS_STATIC_PEERS"
echo "[Perry WSL2 Mirrored] PERRY_API=$PERRY_API"
echo "=================================================="

exec python3 -u /mnt/c/Users/crist/Documents/GitHub/Robot_Claw/perry/perry_ros_bridge.py
