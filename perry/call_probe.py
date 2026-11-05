import rclpy  # type: ignore
from multirobot_interfaces.srv import RequestZone, ReleaseZone  # type: ignore
from multirobot_interfaces.msg import RobotState  # type: ignore

rclpy.init()
node = rclpy.create_node("client_verifier")

cli_req = node.create_client(RequestZone, "/zone/request")
cli_rel = node.create_client(ReleaseZone, "/zone/release")
pub_state = node.create_publisher(RobotState, "/ferb/state", 10)

assert cli_req.wait_for_service(timeout_sec=3.0), "/zone/request no disponible"
assert cli_rel.wait_for_service(timeout_sec=3.0), "/zone/release no disponible"

# 1. Probar publicar estado de Ferb
msg = RobotState()
msg.robot = "ferb"
msg.state = "DELIVERING"
msg.carrying = True
msg.delivered = 1
msg.gate_closed = False
pub_state.publish(msg)
print("[OK] /ferb/state publicado hacia Perry.")

# 2. Probar pedir zona (/zone/request)
req = RequestZone.Request()
req.robot = "ferb"
future = cli_req.call_async(req)
rclpy.spin_until_future_complete(node, future, timeout_sec=3.0)
res = future.result()
print(f"[OK] /zone/request respuesta: granted={res.granted}, holder='{res.holder}', lease={res.lease_seconds}s")

# 3. Probar liberar zona (/zone/release)
rel = ReleaseZone.Request()
rel.robot = "ferb"
rel.delivered = False
future2 = cli_rel.call_async(rel)
rclpy.spin_until_future_complete(node, future2, timeout_sec=3.0)
res2 = future2.result()
print(f"[OK] /zone/release respuesta: ok={res2.ok}, delivered_total={res2.delivered_total}")

node.destroy_node()
rclpy.shutdown()
