"""El panel no lanza el ciclo apenas un carro devuelve la llave: pasa por ASENTANDO (fleet_step).

Con fotos reales: zona vacía = despejada; brazo sobre la zona = objeto grande (como un carro trabado).
"""
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import audit_web  # noqa: E402
from audit_web import S, fleet_step  # noqa: E402
from zone_arbiter import PerryState, ZoneArbiter  # noqa: E402


def load(name):
    return cv2.imdecode(np.frombuffer((HERE / "images" / name).read_bytes(), np.uint8), cv2.IMREAD_COLOR)


EMPTY = load("brazo_estacionado_zona_vacia.jpg")
CUBE = load("brazo_estacionado_cubo_amarillo.jpg")
BIG = load("brazo_sobre_zona.jpg")      # objeto grande en la zona (como la pala de un carro trabado)


@pytest.fixture(autouse=True)
def state():
    S.cfg = yaml.safe_load((HERE.parent / "config" / "arm.yaml").read_text(encoding="utf-8"))
    S.arbiter = ZoneArbiter(initial_state=PerryState.FREE)
    S.arbiter.set_parked_ok(True)
    S.running = False
    S.settle = None
    S.prev_frame = None
    S.log = []
    yield
    S.settle = None


def deliver(t):
    """Un carro toma la llave y la devuelve con un cubo en t."""
    assert S.arbiter.request_zone("ferb", now=t)[0]
    assert S.arbiter.release_zone("ferb", delivered=True, color="yellow", now=t)[0]


def test_release_does_not_start_the_cycle_immediately():
    launched = []
    deliver(100.0)
    fleet_step(100.0, CUBE, launch=lambda: launched.append(True))
    fleet_step(101.0, CUBE, launch=lambda: launched.append(True))
    assert not launched
    assert S.settle is not None


def test_cycle_starts_after_the_minimum_with_a_clear_still_zone():
    launched = []
    deliver(100.0)
    for t in (100.0, 101.0, 102.0, 102.5):
        fleet_step(t, CUBE, launch=lambda: launched.append(t))
    assert launched == [102.0]
    assert S.settle is None


def test_a_car_left_in_the_zone_blocks_it_instead_of_moving_the_arm():
    launched = []
    deliver(100.0)
    for t in (100.0, 103.0, 106.0, 110.0):
        fleet_step(t, BIG, launch=lambda: launched.append(t))
    assert not launched
    assert S.arbiter.state == PerryState.BLOCKED
    assert any("no se despejó" in line for line in S.log)


def test_moving_scene_delays_the_cycle():
    # ASENTANDO cuenta desde que el panel ve la devolución (a lo sumo una vuelta del bucle, 0,25 s, después)
    launched = []
    deliver(100.0)
    fleet_step(100.0, EMPTY, launch=lambda: launched.append(1))   # ve la devolución
    fleet_step(102.0, CUBE, launch=lambda: launched.append(1))    # pasó el mínimo, pero cambió la imagen
    assert not launched
    fleet_step(102.5, CUBE, launch=lambda: launched.append(1))    # ya quieta
    assert launched


def test_blocked_zone_does_not_reopen_while_a_big_object_is_there():
    # la auto-recuperación de BLOCKED no puede abrir la zona con un carro adentro (no lo ve como cubo)
    S.arbiter.set_state(PerryState.BLOCKED)
    assert not audit_web.blocked_can_reopen(BIG, cubes=[])
    assert audit_web.blocked_can_reopen(EMPTY, cubes=[])
