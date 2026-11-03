"""Pruebas unitarias para reach.py: verificación física de posición de reposo (Fase 1)."""
import sys
from pathlib import Path
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reach import is_energized, is_parked, ensure_parked  # noqa: E402


class DummyMaestro:
    """Simulador de Maestro para pruebas sin hardware conectado."""

    def __init__(self, positions=None, moving=False, raise_on_get=False):
        self.positions = dict(positions or {})
        self.moving = moving
        self.raise_on_get = raise_on_get
        self.calls = []

    def get_us(self, channel):
        if self.raise_on_get:
            raise IOError("Maestro desconectada")
        return self.positions.get(channel, 0)

    def set_us(self, channel, us):
        self.calls.append(("set_us", channel, us))
        self.positions[channel] = us

    def is_moving(self):
        return self.moving

    def wait(self, timeout=8.0):
        self.calls.append(("wait", timeout))
        return True

    def set_speed(self, channel, speed):
        self.calls.append(("set_speed", channel, speed))

    def set_acceleration(self, channel, accel):
        self.calls.append(("set_acceleration", channel, accel))


@pytest.fixture
def cfg():
    path = Path(__file__).resolve().parent.parent / "config" / "arm.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_is_energized_all_active(cfg):
    positions = {0: 1500, 2: 1450, 4: 1300, 6: 2000, 8: 1447, 10: 750}
    m = DummyMaestro(positions)
    assert is_energized(m, cfg) is True


def test_is_energized_joint_zero(cfg):
    positions = {0: 1500, 2: 0, 4: 1300, 6: 2000, 8: 1447, 10: 750}  # hombro en 0
    m = DummyMaestro(positions)
    assert is_energized(m, cfg) is False


def test_is_energized_gripper_zero(cfg):
    positions = {0: 1500, 2: 1450, 4: 1300, 6: 2000, 8: 1447, 10: 0}  # pinza en 0
    m = DummyMaestro(positions)
    assert is_energized(m, cfg) is False


def test_is_energized_empty_or_negative(cfg):
    m_empty = DummyMaestro({})
    assert is_energized(m_empty, cfg) is False

    positions_neg = {0: 1500, 2: 1450, 4: 1300, 6: 2000, 8: -5, 10: 750}
    m_neg = DummyMaestro(positions_neg)
    assert is_energized(m_neg, cfg) is False


def test_is_energized_handles_exception(cfg):
    m_err = DummyMaestro(raise_on_get=True)
    assert is_energized(m_err, cfg) is False


def test_is_parked_exact(cfg):
    positions = {
        0: cfg["poses"]["vista"]["base"],
        2: cfg["travel"]["hombro"],
        4: cfg["travel"]["codo"],
        6: cfg["travel"]["muneca"],
        8: 1447,
        10: 750,
    }
    m = DummyMaestro(positions)
    assert is_parked(m, cfg) is True


def test_is_parked_within_tolerance(cfg):
    tol = 30
    positions = {
        0: cfg["poses"]["vista"]["base"] - 25,
        2: cfg["travel"]["hombro"] + 25,
        4: cfg["travel"]["codo"] - 20,
        6: cfg["travel"]["muneca"] + 15,
        8: 1447,
        10: 750,
    }
    m = DummyMaestro(positions)
    assert is_parked(m, cfg, tol_us=tol) is True


def test_is_parked_exceeds_tolerance(cfg):
    positions = {
        0: cfg["poses"]["vista"]["base"],
        2: cfg["travel"]["hombro"] + 45,  # fuera de ±30 us
        4: cfg["travel"]["codo"],
        6: cfg["travel"]["muneca"],
        8: 1447,
        10: 750,
    }
    m = DummyMaestro(positions)
    assert is_parked(m, cfg, tol_us=30) is False

    # Base fuera de tolerancia
    positions[2] = cfg["travel"]["hombro"]
    positions[0] = cfg["poses"]["vista"]["base"] - 50
    m_base = DummyMaestro(positions)
    assert is_parked(m_base, cfg, tol_us=30) is False


def test_is_parked_moving_returns_false(cfg):
    positions = {
        0: cfg["poses"]["vista"]["base"],
        2: cfg["travel"]["hombro"],
        4: cfg["travel"]["codo"],
        6: cfg["travel"]["muneca"],
        8: 1447,
        10: 750,
    }
    m = DummyMaestro(positions, moving=True)
    assert is_parked(m, cfg) is False


def test_is_parked_unenergized_returns_false(cfg):
    positions = {
        0: 0,
        2: cfg["travel"]["hombro"],
        4: cfg["travel"]["codo"],
        6: cfg["travel"]["muneca"],
        8: 1447,
        10: 750,
    }
    m = DummyMaestro(positions)
    assert is_parked(m, cfg) is False


def test_ensure_parked_when_unenergized_does_not_move(cfg):
    positions = {0: 0, 2: 0, 4: 0, 6: 0, 8: 0, 10: 0}
    m = DummyMaestro(positions)
    assert ensure_parked(m, cfg) is False
    # No debe haber mandado ningún comando de set_us
    assert not any(c[0] == "set_us" for c in m.calls)


def test_ensure_parked_when_already_parked_does_not_move(cfg):
    positions = {
        0: cfg["poses"]["vista"]["base"],
        2: cfg["travel"]["hombro"],
        4: cfg["travel"]["codo"],
        6: cfg["travel"]["muneca"],
        8: 1447,
        10: 750,
    }
    m = DummyMaestro(positions)
    assert ensure_parked(m, cfg) is True
    assert not any(c[0] == "set_us" for c in m.calls)


def test_ensure_parked_when_unparked_moves_and_succeeds(cfg):
    test_cfg = dict(cfg)
    test_cfg["park_settle_s"] = 0.0  # evitar sleep en pruebas rápidas
    # Brazo en otra postura cualquiera pero energizado
    positions = {0: 1500, 2: 1200, 4: 1100, 6: 1800, 8: 1447, 10: 750}
    m = DummyMaestro(positions)
    assert ensure_parked(m, test_cfg) is True
    # Comprobar que terminó en travel + vista
    assert m.positions[0] == cfg["poses"]["vista"]["base"]
    assert m.positions[2] == cfg["travel"]["hombro"]
    assert m.positions[4] == cfg["travel"]["codo"]
    assert m.positions[6] == cfg["travel"]["muneca"]
