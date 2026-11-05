"""Pruebas unitarias para perry_ros_bridge.py: resolución de URLs, callbacks y publicación."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import perry_ros_bridge  # noqa: E402
from perry_ros_bridge import PerryRosBridge, resolve_api_url  # noqa: E402


def test_resolve_api_url_env_var(monkeypatch):
    """Si PERRY_API está en variables de entorno y responde, la usa."""
    monkeypatch.setenv("PERRY_API", "http://custom-host:8000")
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_url.return_value = mock_resp
        url = resolve_api_url()
        assert url == "http://custom-host:8000"


def test_bridge_handle_request():
    """Prueba el callback _handle_request ante respuesta positiva de la API."""
    bridge = PerryRosBridge(api_url="http://fake-api:8000", auto_start=False, init_node=False)

    req = MagicMock()
    req.robot = "ferb"
    res = MagicMock()

    with patch.object(bridge, "_api_post", return_value={"granted": True, "holder": "ferb", "remaining_s": 58.5}):
        result = bridge._handle_request(req, res)
        assert result.granted is True
        assert result.holder == "ferb"
        assert result.lease_seconds == 58.5


def test_bridge_handle_release():
    """Prueba el callback _handle_release notificando entrega."""
    bridge = PerryRosBridge(api_url="http://fake-api:8000", auto_start=False, init_node=False)

    req = MagicMock()
    req.robot = "phineas"
    req.delivered = True
    req.color = "blue"
    res = MagicMock()

    with patch.object(bridge, "_api_post", return_value={"ok": True, "count": 3}):
        result = bridge._handle_release(req, res)
        assert result.ok is True
        assert result.delivered_total == 3


def test_bridge_handle_robot_state():
    """Prueba la retransmisión de estado de un carro externo a la API."""
    bridge = PerryRosBridge(api_url="http://fake-api:8000", auto_start=False, init_node=False)

    msg = MagicMock()
    msg.state = "SEARCHING"
    msg.carrying = False
    msg.delivered = 2
    msg.gate_closed = True

    with patch.object(bridge, "_api_post") as mock_post:
        bridge._handle_robot_state("ferb", msg)
        mock_post.assert_called_once_with(
            "/robot_state",
            {
                "robot": "ferb",
                "state": "SEARCHING",
                "carrying": False,
                "delivered": 2,
                "gate_closed": True,
            },
            timeout=1.0,
        )


def test_bridge_publish_state_with_data():
    """Prueba que _publish_state construye y publica los mensajes ROS esperados."""
    bridge = PerryRosBridge(api_url="http://fake-api:8000", auto_start=False, init_node=False)
    bridge._occupant_pub = MagicMock()
    bridge._state_pub = MagicMock()

    bridge._latest_status = {
        "arbiter": {
            "state": "FREE",
            "occupant_msg": "",
            "occupant": "",
            "carrying": False,
            "sorted_total": 4,
            "gate_closed": False,
        }
    }

    mock_robot_state = MagicMock()
    mock_string = MagicMock()
    with patch("perry_ros_bridge.RobotState", mock_robot_state), patch("perry_ros_bridge.String", mock_string):
        bridge._publish_state()
        assert bridge._occupant_pub.publish.called
        assert bridge._state_pub.publish.called
