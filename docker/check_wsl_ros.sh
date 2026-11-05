#!/usr/bin/env bash
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

echo "=== IP EN WSL ==="
hostname -I
echo "=== ROS 2 NODE LIST ==="
ros2 node list --no-daemon
echo "=== ROS 2 TOPIC LIST ==="
ros2 topic list --no-daemon
echo "=== /zone/occupant ==="
ros2 topic echo /zone/occupant --once --no-daemon
