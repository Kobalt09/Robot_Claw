"""Pruebas unitarias para sort_cubes.py: integración con ZoneArbiter (Fase 3)."""
import sys
import threading
from pathlib import Path

import numpy as np
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from grasp import Cube  # noqa: E402
from sort_cubes import sort_loop  # noqa: E402
from zone_arbiter import PerryState, ZoneArbiter  # noqa: E402


class DummyMaestro:
    def __init__(self, energized=True, parked=True):
        self.calls = []
        if energized and parked:
            self.positions = {0: 2100, 2: 1450, 4: 1300, 6: 2000, 8: 1447, 10: 750}
        elif energized:
            self.positions = {0: 1500, 2: 1200, 4: 1100, 6: 1800, 8: 1447, 10: 750}
        else:
            self.positions = {0: 0, 2: 0, 4: 0, 6: 0, 8: 0, 10: 0}

    def get_us(self, channel):
        return self.positions.get(channel, 0)

    def set_us(self, channel, us):
        self.calls.append(("set_us", channel, us))
        self.positions[channel] = us

    def is_moving(self):
        return False

    def wait(self, timeout=8.0):
        return True

    def set_speed(self, channel, speed):
        pass

    def set_acceleration(self, channel, accel):
        pass

    def close(self):
        pass


import cv2


class DummyCamera:
    def __init__(self, cfg, sequence=None):
        # sequence: lista de listas de cubos a devolver en llamadas sucesivas a find_cubes()
        self.sequence = list(sequence or [[]])
        self.dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)
        c = cfg["camera"]
        self.H = cv2.getPerspectiveTransform(np.float32(c["corners_px"]), np.float32(c["corners_cm"]))
        self.nadir = (15.0, 0.0)

    def find_cubes(self):
        if self.sequence:
            cubes = self.sequence.pop(0)
        else:
            cubes = []
        return cubes, self.dummy_img.copy()


class DummyLog:
    def __init__(self):
        self.messages = []
        self.dir = Path(__file__).parent

    def __call__(self, msg):
        self.messages.append(msg)

    def image(self, name, img):
        pass


@pytest.fixture
def cfg():
    path = Path(__file__).resolve().parent.parent / "config" / "arm.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["park_settle_s"] = 0.0  # evitar demoras de sleep en tests
    return data


def test_sort_loop_refuses_when_receiving(cfg):
    """No debe iniciar si un carro está en la zona entregando (RECEIVING)."""
    arbiter = ZoneArbiter(initial_state=PerryState.RECEIVING)
    m = DummyMaestro()
    cam = DummyCamera(cfg)
    log = DummyLog()

    done = sort_loop(cfg, m, cam, log, run=True, arbiter=arbiter)
    assert done == 0
    assert arbiter.state == PerryState.RECEIVING
    assert any("RECEIVING" in msg for msg in log.messages)


def test_sort_loop_refuses_when_unenergized(cfg):
    """No debe iniciar si los servos están en 0 us (desenergizados)."""
    arbiter = ZoneArbiter(initial_state=PerryState.SCANNING)
    m = DummyMaestro(energized=False)
    cam = DummyCamera(cfg)
    log = DummyLog()

    done = sort_loop(cfg, m, cam, log, run=True, arbiter=arbiter)
    assert done == 0
    assert arbiter.state == PerryState.STOP
    assert arbiter.parked_ok is False
    assert any("no está energizado" in msg for msg in log.messages)


def test_sort_loop_transitions_to_free_when_no_cubes(cfg):
    """Si la zona no tiene cubos y el brazo está en reposo, pasa a FREE (occupant='')."""
    arbiter = ZoneArbiter(initial_state=PerryState.STOP)
    m = DummyMaestro(energized=True, parked=True)
    cam = DummyCamera(cfg, [[]])
    log = DummyLog()

    done = sort_loop(cfg, m, cam, log, run=True, arbiter=arbiter)
    assert done == 0
    assert arbiter.state == PerryState.FREE
    assert arbiter.parked_ok is True
    assert arbiter.occupant_msg == ""


def test_sort_loop_transitions_to_blocked_when_cubes_unreachable(cfg):
    """Si quedan cubos fuera de alcance que no se pueden recoger, pasa a BLOCKED."""
    arbiter = ZoneArbiter(initial_state=PerryState.STOP)
    m = DummyMaestro(energized=True, parked=True)
    # Cubo a 25 cm (fuera de max_r = 19.5 cm)
    cam = DummyCamera(cfg, [[Cube("azul", 25.0, 0.0, 0.0)]])
    log = DummyLog()

    done = sort_loop(cfg, m, cam, log, run=True, arbiter=arbiter)
    assert done == 0
    assert arbiter.state == PerryState.BLOCKED
    assert arbiter.occupant_msg == "perry"


def test_sort_loop_transitions_to_stop_when_cancelled(cfg):
    """Si el usuario cancela durante el ciclo, sube y pasa a STOP."""
    arbiter = ZoneArbiter(initial_state=PerryState.SCANNING)
    m = DummyMaestro(energized=True, parked=True)
    cam = DummyCamera(cfg, [[Cube("azul", 15.0, 0.0, 0.0)]])
    log = DummyLog()
    stop = threading.Event()
    stop.set()  # Cancelado inmediatamente

    sort_loop(cfg, m, cam, log, run=True, stop=stop, arbiter=arbiter)
    assert arbiter.state == PerryState.STOP
    assert arbiter.occupant_msg == "perry"


def test_sort_loop_full_pick_state_sequence(cfg):
    """Ciclo con agarre exitoso: valida la secuencia SCANNING -> PICKING -> DROPPING -> FREE."""
    arbiter = ZoneArbiter(initial_state=PerryState.STOP)
    m = DummyMaestro(energized=True, parked=True)
    history = []

    original_set_state = arbiter.set_state

    def track_set_state(st, carrying=None, parked_ok=None):
        history.append((st, carrying, parked_ok))
        original_set_state(st, carrying, parked_ok)

    arbiter.set_state = track_set_state

    # Secuencia de cámara:
    # 1. Escaneo inicial: 1 cubo azul alcanzable en (15.35, 0)
    # 2. Verificación post-agarre: 0 cubos en la mesa (agarre exitoso)
    # 3. Escaneo del siguiente ciclo: 0 cubos restantes en la mesa
    cube = Cube("azul", 15.35, 0.0, 0.0)
    cam = DummyCamera(cfg, [[cube], [], []])
    log = DummyLog()

    done = sort_loop(cfg, m, cam, log, run=True, arbiter=arbiter)
    assert done == 1
    assert arbiter.sorted_total == 1
    assert arbiter.state == PerryState.FREE
    assert arbiter.occupant_msg == ""

    # Verificar que pasó por SCANNING, PICKING, DROPPING y FREE
    states_visited = [h[0] for h in history]
    assert PerryState.SCANNING in states_visited
    assert PerryState.PICKING in states_visited
    assert PerryState.DROPPING in states_visited
    assert PerryState.FREE in states_visited

    # Verificar que DROPPING tuvo carrying=True
    dropping_entries = [h for h in history if h[0] == PerryState.DROPPING]
    assert any(h[1] is True for h in dropping_entries)
