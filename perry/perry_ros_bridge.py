"""Perry ROS 2 Bridge: conecta la red ROS 2 de la flota con el servidor web local de Perry.

Expone para Ferb y Phineas:
- /zone/occupant (std_msgs/msg/String, 2 Hz, RELIABLE + TRANSIENT_LOCAL depth 1)
- /perry/state (multirobot_interfaces/msg/RobotState, 2 Hz)
- /zone/request (multirobot_interfaces/srv/RequestZone)
- /zone/release (multirobot_interfaces/srv/ReleaseZone)
- /ferb/state y /phineas/state (suscriptor de estado de carros)
"""
import json
import os
import sys
import threading
import time
from typing import Any
import urllib.request
import urllib.error

rclpy: Any = None
Node: Any = object
QoSProfile: Any = None
ReliabilityPolicy: Any = None
DurabilityPolicy: Any = None
HistoryPolicy: Any = None
String: Any = None
RobotState: Any = None
RequestZone: Any = None
ReleaseZone: Any = None

try:
    import rclpy as _rclpy  # type: ignore
    from rclpy.node import Node as _Node  # type: ignore
    from rclpy.qos import (  # type: ignore
        QoSProfile as _QoSProfile,
        ReliabilityPolicy as _ReliabilityPolicy,
        DurabilityPolicy as _DurabilityPolicy,
        HistoryPolicy as _HistoryPolicy,
    )
    from std_msgs.msg import String as _String  # type: ignore
    from multirobot_interfaces.msg import RobotState as _RobotState  # type: ignore
    from multirobot_interfaces.srv import (  # type: ignore
        RequestZone as _RequestZone,
        ReleaseZone as _ReleaseZone,
    )

    rclpy = _rclpy
    Node = _Node
    QoSProfile = _QoSProfile
    ReliabilityPolicy = _ReliabilityPolicy
    DurabilityPolicy = _DurabilityPolicy
    HistoryPolicy = _HistoryPolicy
    String = _String
    RobotState = _RobotState
    RequestZone = _RequestZone
    ReleaseZone = _ReleaseZone
    HAS_RCLPY = True
except ImportError:
    HAS_RCLPY = False


def resolve_api_url():
    """Resuelve la URL del panel web priorizando PERRY_API sin bloqueos innecesarios."""
    env_url = os.environ.get("PERRY_API")
    if env_url:
        return env_url.rstrip("/")

    candidates = [
        "http://172.25.32.1:8000",
        "http://host.docker.internal:8000",
        "http://127.0.0.1:8000",
    ]
    for url in candidates:
        try:
            req = urllib.request.urlopen(f"{url}/status", timeout=0.8)
            if req.status == 200:
                return url
        except Exception:
            pass
    return "http://172.25.32.1:8000"


class PerryRosBridge(Node):  # type: ignore[misc, valid-type]
    def __init__(self, api_url=None, auto_start=True, init_node=True):
        if init_node and HAS_RCLPY and Node is not object:
            if not rclpy.ok():
                rclpy.init()
            super().__init__("perry_fleet_node")
            logger = self.get_logger()
        else:
            logger = None

        self._logger = logger
        self.api_url = api_url or resolve_api_url()
        self._log_info(f"Iniciando PerryRosBridge conectado a {self.api_url}...")

        # Estado en memoria desacoplado del I/O HTTP
        self._lock = threading.Lock()
        self._latest_status = None
        self._running = True

        if init_node and HAS_RCLPY and Node is not object:
            # QoS para /zone/occupant: RELIABLE + TRANSIENT_LOCAL (depth 1)
            occ_qos = QoSProfile(
                history=HistoryPolicy.KEEP_LAST,
                depth=1,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.TRANSIENT_LOCAL,
            )
            self._occupant_pub = self.create_publisher(String, "/zone/occupant", occ_qos)

            # QoS para /perry/state (RELIABLE + TRANSIENT_LOCAL es compatible tanto con suscriptores VOLATILE como TRANSIENT_LOCAL)
            state_qos = QoSProfile(
                history=HistoryPolicy.KEEP_LAST,
                depth=1,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.TRANSIENT_LOCAL,
            )
            self._state_pub = self.create_publisher(RobotState, "/perry/state", state_qos)

            # Servicios de zona
            self._req_srv = self.create_service(RequestZone, "/zone/request", self._handle_request)
            self._rel_srv = self.create_service(ReleaseZone, "/zone/release", self._handle_release)

            # Suscriptores de estado de Ferb y Phineas
            self._sub_ferb = self.create_subscription(
                RobotState, "/ferb/state", lambda msg: self._handle_robot_state("ferb", msg), 10
            )
            self._sub_phineas = self.create_subscription(
                RobotState, "/phineas/state", lambda msg: self._handle_robot_state("phineas", msg), 10
            )

            # Loop de publicación ROS a 2 Hz (0.5 s) completamente no bloqueante
            self._timer = self.create_timer(0.5, self._publish_state)
        else:
            self._occupant_pub = None
            self._state_pub = None
            self._req_srv = None
            self._rel_srv = None
            self._sub_ferb = None
            self._sub_phineas = None
            self._timer = None

        # Hilo en segundo plano para consultar /status de forma asíncrona sin bloquear ROS 2
        if auto_start:
            self._poll_thread = threading.Thread(target=self._status_polling_loop, daemon=True)
            self._poll_thread.start()
        else:
            self._poll_thread = None

    def _log_info(self, msg):
        if self._logger:
            self._logger.info(msg)
        else:
            print(f"[INFO] {msg}")

    def _log_warn(self, msg, throttle_duration_sec=0.0):
        if self._logger:
            if throttle_duration_sec > 0:
                self._logger.warn(msg, throttle_duration_sec=throttle_duration_sec)
            else:
                self._logger.warn(msg)
        else:
            print(f"[WARN] {msg}")

    def _log_error(self, msg):
        if self._logger:
            self._logger.error(msg)
        else:
            print(f"[ERROR] {msg}")

    def _status_polling_loop(self):
        """Consulta el estado del servidor web periódicamente con backoff ante fallos."""
        consecutive_failures = 0
        while self._running:
            try:
                req = urllib.request.urlopen(f"{self.api_url}/status", timeout=1.5)
                data = json.loads(req.read().decode())
                with self._lock:
                    self._latest_status = data
                if consecutive_failures > 0:
                    self._log_info(f"Reconexión exitosa con Perry web en {self.api_url}")
                    consecutive_failures = 0
                time.sleep(0.4)
            except Exception as e:
                consecutive_failures += 1
                self._log_warn(
                    f"Conexión con Perry web ({self.api_url}) interrumpida: {e}",
                    throttle_duration_sec=10.0
                )
                time.sleep(min(2.5, 0.5 * consecutive_failures))

    def _api_post(self, endpoint, payload, timeout=1.5):
        try:
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{self.api_url}{endpoint}",
                data=data,
                headers={"Content-Type": "application/json"}
            )
            res = urllib.request.urlopen(req, timeout=timeout)
            return json.loads(res.read().decode())
        except Exception as e:
            self._log_error(f"Error POST {endpoint}: {e}")
            return {}

    def _publish_state(self):
        with self._lock:
            status = self._latest_status

        if not status:
            if self._occupant_pub and String:
                occ_msg = String()
                occ_msg.data = "perry"
                self._occupant_pub.publish(occ_msg)
            if self._state_pub and RobotState:
                st_msg = RobotState()
                if hasattr(self, "_clock") and self._clock is not None:
                    st_msg.stamp = self.get_clock().now().to_msg()
                st_msg.robot = "perry"
                st_msg.state = "STOP"
                st_msg.carrying = False
                st_msg.delivered = 0
                st_msg.gate_closed = True
                self._state_pub.publish(st_msg)
            return

        arbiter = status.get("arbiter", {})
        occupant = arbiter.get("occupant_msg", arbiter.get("occupant", "perry"))

        # 1. Publicar /zone/occupant
        if self._occupant_pub and String:
            occ_msg = String()
            occ_msg.data = str(occupant)
            self._occupant_pub.publish(occ_msg)

        # 2. Publicar /perry/state
        if self._state_pub and RobotState:
            st_msg = RobotState()
            if hasattr(self, "_clock") and self._clock is not None:
                st_msg.stamp = self.get_clock().now().to_msg()
            st_msg.robot = "perry"
            st_msg.state = str(arbiter.get("state", "STOP"))
            st_msg.carrying = bool(arbiter.get("carrying", False))
            st_msg.delivered = int(arbiter.get("sorted_total", 0))
            st_msg.gate_closed = bool(arbiter.get("gate_closed", True))
            self._state_pub.publish(st_msg)

    def _handle_request(self, request, response):
        robot = str(request.robot).strip().lower()
        res = self._api_post("/zone_request", {"robot": robot}, timeout=1.5)
        response.granted = bool(res.get("granted", False))
        response.holder = str(res.get("holder", "perry"))
        response.lease_seconds = float(res.get("remaining_s", 0.0))
        self._log_info(f"/zone/request de '{robot}': granted={response.granted}, holder='{response.holder}', lease={response.lease_seconds}s")
        return response

    def _handle_release(self, request, response):
        robot = str(request.robot).strip().lower()
        color = str(getattr(request, "color", "")).strip().lower()
        delivered = bool(request.delivered)
        res = self._api_post("/zone_release", {"robot": robot, "delivered": delivered, "color": color}, timeout=1.5)
        response.ok = bool(res.get("ok", False))
        response.delivered_total = int(res.get("count", 0))
        self._log_info(f"/zone/release de '{robot}' (delivered={delivered}): ok={response.ok}, total={response.delivered_total}")
        return response

    def _handle_robot_state(self, robot_name, msg):
        payload = {
            "robot": robot_name,
            "state": str(msg.state),
            "carrying": bool(msg.carrying),
            "delivered": int(msg.delivered),
            "gate_closed": bool(getattr(msg, "gate_closed", False)),
        }
        self._api_post("/robot_state", payload, timeout=1.0)

    def stop(self):
        self._running = False


def main():
    if not HAS_RCLPY:
        print("[Perry ROS 2 Bridge] Error al importar dependencias de ROS 2.")
        print("Nota: Este script está diseñado para ejecutarse DENTRO del contenedor Docker con ROS 2.")
        print("Para iniciarlo, ejecuta: docker compose -f compose_bridge.yaml up -d")
        sys.exit(1)

    node = PerryRosBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
