"""Pruebas unitarias para audit_web.py: endpoints y lógica de la Fase 5."""
import json
import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import audit_web  # noqa: E402
from audit_web import Handler, S  # noqa: E402
from zone_arbiter import PerryState, ZoneArbiter  # noqa: E402


class MockRequest:
    def __init__(self, body=b""):
        self._body = body

    def makefile(self, *args, **kwargs):
        return BytesIO(self._body)

    def sendall(self, data):
        pass


class MockHTTPHandler(Handler):
    def __init__(self, method, path, body=b""):
        self.rfile = BytesIO(body)
        self.wfile = BytesIO()
        self.command = method
        self.path = path
        self.request_version = "HTTP/1.1"
        self.headers = {"Content-Length": str(len(body))}
        self.server = None
        self.client_address = ("127.0.0.1", 12345)
        self.responses = []

    def send_response(self, code, message=None):
        self.responses.append(code)

    def send_header(self, keyword, value):
        pass

    def end_headers(self):
        pass


@pytest.fixture(autouse=True)
def setup_state():
    S.cfg = yaml.safe_load((Path(__file__).resolve().parent.parent / "config" / "arm.yaml").read_text(encoding="utf-8"))
    S.cfg["park_settle_s"] = 0.0
    S.arbiter = ZoneArbiter(initial_state=PerryState.STOP)
    S.running = False
    S.status = "listo"
    S.cam = MagicMock()
    yield
    S.running = False


def test_status_endpoint_returns_arbiter_and_fleet():
    S.arbiter.set_state(PerryState.FREE, parked_ok=True)
    handler = MockHTTPHandler("GET", "/status")
    handler.do_GET()

    assert 200 in handler.responses
    data = json.loads(handler.wfile.getvalue().decode())
    assert "arbiter" in data
    assert data["arbiter"]["state"] == "FREE"
    assert data["arbiter"]["parked_ok"] is True
    assert "fleet" in data
    assert "ferb" in data["fleet"]
    assert "phineas" in data["fleet"]


def test_block_zone_endpoint():
    S.arbiter.set_state(PerryState.FREE, parked_ok=True)
    handler = MockHTTPHandler("POST", "/block_zone")
    handler.do_POST()

    assert 200 in handler.responses
    assert S.arbiter.state == PerryState.STOP
    assert S.arbiter.parked_ok is False
    assert "STOP" in S.status


def test_enable_zone_rejected_if_cubes_present():
    S.arbiter.set_state(PerryState.STOP)
    # Simular que la cámara ve 2 cubos en la zona
    S.cam.find_cubes.return_value = (["cubo1", "cubo2"], None)

    handler = MockHTTPHandler("POST", "/enable_zone")
    handler.do_POST()

    assert 400 in handler.responses
    assert S.arbiter.state == PerryState.STOP
    body = handler.wfile.getvalue().decode()
    assert "aún quedan 2 cubos" in body


def test_enable_zone_success_when_empty_and_parked(monkeypatch):
    S.arbiter.set_state(PerryState.STOP)
    S.cam.find_cubes.return_value = ([], None)

    # Simular que ensure_parked devuelve True
    monkeypatch.setattr(audit_web, "ensure_parked", lambda m, cfg: True)
    # Mockear open_arm para no requerir hardware serie
    mock_arm = MagicMock()
    monkeypatch.setattr(audit_web, "open_arm", lambda cfg: mock_arm)

    handler = MockHTTPHandler("POST", "/enable_zone")
    handler.do_POST()

    assert 200 in handler.responses
    assert S.arbiter.state == PerryState.FREE
    assert S.arbiter.parked_ok is True
    assert S.arbiter.occupant_msg == ""


def test_enable_zone_rejected_when_running():
    S.running = True
    handler = MockHTTPHandler("POST", "/enable_zone")
    handler.do_POST()
    assert 400 in handler.responses
    assert "Perry está en marcha" in handler.wfile.getvalue().decode()


def test_enable_zone_rejected_when_camera_none():
    S.cam = None
    handler = MockHTTPHandler("POST", "/enable_zone")
    handler.do_POST()
    assert 503 in handler.responses
    assert "cámara cenital no está lista" in handler.wfile.getvalue().decode()


def test_enable_zone_fails_when_serial_error(monkeypatch):
    S.arbiter.set_state(PerryState.STOP)
    S.cam.find_cubes.return_value = ([], None)
    monkeypatch.setattr(audit_web, "open_arm", MagicMock(side_effect=IOError("Puerto COM no encontrado")))

    handler = MockHTTPHandler("POST", "/enable_zone")
    handler.do_POST()
    assert 500 in handler.responses
    assert "Error de comunicación con la Maestro" in handler.wfile.getvalue().decode()


def test_enable_zone_fails_when_ensure_parked_false(monkeypatch):
    S.arbiter.set_state(PerryState.STOP)
    S.cam.find_cubes.return_value = ([], None)
    monkeypatch.setattr(audit_web, "open_arm", lambda cfg: MagicMock())
    monkeypatch.setattr(audit_web, "ensure_parked", lambda m, cfg: False)

    handler = MockHTTPHandler("POST", "/enable_zone")
    handler.do_POST()
    assert 500 in handler.responses
    assert S.arbiter.state == PerryState.STOP
    assert S.arbiter.parked_ok is False


def test_start_and_stop_endpoints():
    # Start con cámara None
    S.cam = None
    h1 = MockHTTPHandler("POST", "/start", body=b"run")
    h1.do_POST()
    assert "cámara todavía no está lista" in h1.wfile.getvalue().decode()

    # Stop sin ciclo en marcha: se registra y se ignora (31-10: un Cancelar fantasma llegaba sin ciclo)
    S.running = False
    S.stop.clear()
    h2 = MockHTTPHandler("POST", "/stop")
    h2.do_POST()
    assert not S.stop.is_set()
    assert "se ignora" in S.log[-1]

    # Stop con ciclo en marcha: pide la parada
    S.running = True
    try:
        h3 = MockHTTPHandler("POST", "/stop")
        h3.do_POST()
        assert S.stop.is_set()
        assert "cancelando" in S.status
    finally:
        S.running = False
        S.stop.clear()


def test_bridge_api_endpoints():
    """Valida los endpoints HTTP usados por el puente ROS 2."""
    # 1. /robot_state
    body = json.dumps({
        "robot": "ferb",
        "state": "SEARCHING",
        "carrying": True,
        "delivered": 5,
        "gate_closed": False,
    }).encode("utf-8")
    h_state = MockHTTPHandler("POST", "/robot_state", body=body)
    h_state.do_POST()
    assert 200 in h_state.responses
    fleet = audit_web.get_fleet_state()
    assert fleet["ferb"]["state"] == "SEARCHING"
    assert fleet["ferb"]["carrying"] is True
    assert fleet["ferb"]["delivered"] == 5

    # 2. /zone_request
    S.arbiter.set_state(PerryState.FREE, parked_ok=True)
    body_req = json.dumps({"robot": "ferb"}).encode("utf-8")
    h_req = MockHTTPHandler("POST", "/zone_request", body=body_req)
    h_req.do_POST()
    assert 200 in h_req.responses
    res_req = json.loads(h_req.wfile.getvalue().decode())
    assert res_req["granted"] is True
    assert res_req["holder"] == "ferb"

    # 3. /zone_release
    body_rel = json.dumps({"robot": "ferb", "delivered": True, "color": "azul"}).encode("utf-8")
    h_rel = MockHTTPHandler("POST", "/zone_release", body=body_rel)
    h_rel.do_POST()
    assert 200 in h_rel.responses
    res_rel = json.loads(h_rel.wfile.getvalue().decode())
    assert res_rel["ok"] is True
    assert res_rel["count"] == 1


if __name__ == "__main__":
    pytest.main([__file__])

