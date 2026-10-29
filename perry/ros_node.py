"""Nodo ROS 2 para la flota multirobot: publica estado de Perry y árbitro de zona.

Expone los tópicos y servicios de ROS 2 esperados por Ferb y Phineas:
- Publicador /zone/occupant (std_msgs/msg/String, 2 Hz, RELIABLE, TRANSIENT_LOCAL)
- Publicador /perry/state (multirobot_interfaces/msg/RobotState, 2 Hz)
- Servicio /zone/request (multirobot_interfaces/srv/RequestZone)
- Servicio /zone/release (multirobot_interfaces/srv/ReleaseZone)
- Suscriptores /ferb/state y /phineas/state (RobotState)

Si rclpy o multirobot_interfaces no están instalados (ej. en desarrollo local sin Docker),
el módulo funciona en modo degradado sin arrojar excepciones.
"""
import threading
import time
from typing import Optional, Dict, Any

from zone_arbiter import PerryState, ZoneArbiter

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
    from std_msgs.msg import String

    try:
        from multirobot_interfaces.msg import RobotState
        from multirobot_interfaces.srv import RequestZone, ReleaseZone
        HAS_INTERFACES = True
    except ImportError:
        HAS_INTERFACES = False
    HAS_RCLPY = True
except ImportError:
    HAS_RCLPY = False
    HAS_INTERFACES = False


# Almacén de estado de la flota para consulta desde el panel web
_fleet_lock = threading.Lock()
_fleet_states: Dict[str, Dict[str, Any]] = {
    "ferb": {
        "robot": "ferb",
        "state": "desconectado",
        "carrying": False,
        "delivered": 0,
        "gate_closed": False,
        "updated_at": 0.0,
    },
    "phineas": {
        "robot": "phineas",
        "state": "desconectado",
        "carrying": False,
        "delivered": 0,
        "gate_closed": False,
        "updated_at": 0.0,
    },
}


def get_fleet_state() -> Dict[str, Dict[str, Any]]:
    """Devuelve un clon consistente del estado actual de Ferb y Phineas."""
    with _fleet_lock:
        return {k: dict(v) for k, v in _fleet_states.items()}


def update_robot_state(robot_name: str, state: str, carrying: bool, delivered: int, gate_closed: bool = False):
    """Actualiza manualmente o por mensaje el estado de un robot recolector."""
    with _fleet_lock:
        if robot_name in _fleet_states:
            _fleet_states[robot_name].update({
                "state": state,
                "carrying": carrying,
                "delivered": delivered,
                "gate_closed": gate_closed,
                "updated_at": time.time(),
            })


if HAS_RCLPY:
    class PerryFleetNode(Node):
        """Nodo ROS 2 para coordinar la zona de entrega y publicar el estado de Perry."""

        def __init__(self, arbiter: ZoneArbiter, publish_rate_hz: float = 2.0):
            super().__init__("perry_fleet_node")
            self.arbiter = arbiter
            self.get_logger().info("Iniciando PerryFleetNode para coordinación multirobot...")

            # QoS para /zone/occupant (RELIABLE + TRANSIENT_LOCAL depth=1)
            occupant_qos = QoSProfile(
                history=HistoryPolicy.KEEP_LAST,
                depth=1,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.TRANSIENT_LOCAL,
            )
            self._occupant_pub = self.create_publisher(String, "/zone/occupant", occupant_qos)

            # Publicador /perry/state
            if HAS_INTERFACES:
                state_qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=5, reliability=ReliabilityPolicy.RELIABLE)
                self._state_pub = self.create_publisher(RobotState, "/perry/state", state_qos)

                # Servicios de zona
                self._request_srv = self.create_service(RequestZone, "/zone/request", self._handle_request_zone)
                self._release_srv = self.create_service(ReleaseZone, "/zone/release", self._handle_release_zone)

                # Suscriptores de estado de Ferb y Phineas
                self._sub_ferb = self.create_subscription(
                    RobotState, "/ferb/state", lambda msg: self._handle_robot_state("ferb", msg), 10
                )
                self._sub_phineas = self.create_subscription(
                    RobotState, "/phineas/state", lambda msg: self._handle_robot_state("phineas", msg), 10
                )
            else:
                self.get_logger().warn("multirobot_interfaces no encontrado; servicios y /perry/state no registrados.")

            # Temporizador de publicación a 2 Hz
            period = 1.0 / max(0.1, publish_rate_hz)
            self._timer = self.create_timer(period, self._publish_loop)

            # Temporizador de tick para chequeo de leases (5 Hz)
            self._tick_timer = self.create_timer(0.2, self._tick_loop)

        def _publish_loop(self):
            # 1. Publicar /zone/occupant
            occ_msg = String()
            occ_msg.data = self.arbiter.occupant_msg
            self._occupant_pub.publish(occ_msg)

            # 2. Publicar /perry/state si las interfaces están disponibles
            if HAS_INTERFACES:
                st_msg = RobotState()
                st_msg.robot = "perry"
                st_msg.state = self.arbiter.state.value
                st_msg.carrying = bool(self.arbiter.carrying)
                st_msg.delivered = int(self.arbiter.sorted_total)
                st_msg.gate_closed = bool(self.arbiter.state == PerryState.BLOCKED)
                self._state_pub.publish(st_msg)

        def _tick_loop(self):
            self.arbiter.tick()

        def _handle_request_zone(self, request, response):
            robot = str(request.robot).strip().lower()
            granted, holder, remaining_s = self.arbiter.request_zone(robot)
            response.granted = bool(granted)
            response.holder = str(holder)
            response.remaining_s = float(remaining_s)
            self.get_logger().info(f"/zone/request de '{robot}': granted={granted}, holder='{holder}'")
            return response

        def _handle_release_zone(self, request, response):
            robot = str(request.robot).strip().lower()
            color = str(getattr(request, "color", "")).strip().lower()
            ok, count = self.arbiter.release_zone(robot, delivered=bool(request.delivered), color=color)
            response.ok = bool(ok)
            response.count = int(count)
            self.get_logger().info(f"/zone/release de '{robot}' (delivered={request.delivered}): ok={ok}, total={count}")
            return response

        def _handle_robot_state(self, robot_name: str, msg):
            update_robot_state(
                robot_name=robot_name,
                state=msg.state,
                carrying=msg.carrying,
                delivered=msg.delivered,
                gate_closed=getattr(msg, "gate_closed", False),
            )
else:
    PerryFleetNode = None  # type: ignore


def start_ros_node(arbiter: ZoneArbiter, publish_rate_hz: float = 2.0) -> Optional[Any]:
    """Inicia el nodo ROS 2 en un hilo secundario si rclpy está disponible."""
    if not HAS_RCLPY or PerryFleetNode is None:
        print("[ROS 2] rclpy no está instalado o no se puede importar; funcionando en modo local.")
        return None

    try:
        if not rclpy.ok():
            rclpy.init()
        node = PerryFleetNode(arbiter, publish_rate_hz=publish_rate_hz)

        def _spin():
            try:
                rclpy.spin(node)
            except Exception as e:
                print(f"[ROS 2 Error en spin] {e}")

        t = threading.Thread(target=_spin, daemon=True, name="PerryROS2Spin")
        t.start()
        print("[ROS 2] PerryFleetNode iniciado correctamente en hilo daemon.")
        return node
    except Exception as e:
        print(f"[ROS 2] Error al iniciar nodo: {e}")
        return None
