"""Pruebas unitarias para ros_node.py (Fase 4): interfaces, callbacks y fallback sin rclpy."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ros_node  # noqa: E402
from ros_node import get_fleet_state, update_robot_state, start_ros_node  # noqa: E402
from zone_arbiter import PerryState, ZoneArbiter  # noqa: E402


def test_fleet_state_initial_and_update():
    """Valida lectura y actualización del estado de Ferb y Phineas."""
    state = get_fleet_state()
    assert "ferb" in state
    assert "phineas" in state

    # Actualizar estado de Ferb
    update_robot_state("ferb", state="SEARCHING", carrying=True, delivered=2, gate_closed=False)
    updated = get_fleet_state()
    assert updated["ferb"]["state"] == "SEARCHING"
    assert updated["ferb"]["carrying"] is True
    assert updated["ferb"]["delivered"] == 2
    assert updated["ferb"]["updated_at"] > 0


def test_start_ros_node_fallback_when_no_rclpy(monkeypatch):
    """Si rclpy no está instalado, start_ros_node devuelve None sin lanzar excepción."""
    monkeypatch.setattr(ros_node, "HAS_RCLPY", False)
    arbiter = ZoneArbiter()
    node = start_ros_node(arbiter)
    assert node is None


def test_node_request_and_release_callbacks():
    """Prueba la lógica interna de los callbacks de servicio simulando las solicitudes de ROS."""
    arbiter = ZoneArbiter()
    arbiter.set_state(PerryState.FREE, parked_ok=True)

    # Simular objeto solicitud y respuesta de RequestZone
    req = MagicMock()
    req.robot = "ferb"
    res = MagicMock()

    # Callback de request_zone
    granted, holder, remaining = arbiter.request_zone(req.robot)
    res.granted = granted
    res.holder = holder
    res.lease_seconds = remaining

    assert res.granted is True
    assert res.holder == "ferb"
    assert res.lease_seconds == 60.0
    assert arbiter.state == PerryState.RECEIVING

    # Callback de release_zone
    rel_req = MagicMock()
    rel_req.robot = "ferb"
    rel_req.delivered = True
    rel_req.color = "blue"
    rel_res = MagicMock()

    ok, total = arbiter.release_zone(rel_req.robot, delivered=rel_req.delivered, color=rel_req.color)
    rel_res.ok = ok
    rel_res.delivered_total = total

    assert rel_res.ok is True
    assert rel_res.delivered_total == 1
    assert arbiter.state == PerryState.SCANNING
    assert arbiter.trigger_sort is True


def test_node_handles_foreign_robot_state():
    """Prueba la actualización ante un mensaje RobotState de Ferb."""
    msg = MagicMock()
    msg.state = "DELIVERING"
    msg.carrying = True
    msg.delivered = 3
    msg.gate_closed = False

    update_robot_state("ferb", msg.state, msg.carrying, msg.delivered, msg.gate_closed)
    state = get_fleet_state()
    assert state["ferb"]["state"] == "DELIVERING"
    assert state["ferb"]["carrying"] is True
    assert state["ferb"]["delivered"] == 3
