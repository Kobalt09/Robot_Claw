"""Turnos de la zona (plan de integración del 02-11, puntos 5.2 y 5.4):

- gate_closed («no traigan más») con la zona llena, bloqueada o detenida por el operador;
- cola de llegada: si los dos carros esperan, la llave va al que la pidió primero;
- Perry cede la llave después de un cubo si un carro espera y en la mesa quedan pocos cubos.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from grasp import Cube  # noqa: E402
from sort_cubes import sort_loop  # noqa: E402
from test_sort_arbiter import DummyCamera, DummyLog, DummyMaestro, cfg  # noqa: E402,F401
from zone_arbiter import PerryState, ZoneArbiter  # noqa: E402


def free_arbiter(**kw):
    a = ZoneArbiter(initial_state=PerryState.FREE, full_cubes=2, queue_ttl_s=3.0, **kw)
    a.set_parked_ok(True)
    return a


# --- gate_closed ---

def test_gate_is_closed_when_stopped_or_blocked():
    for st in (PerryState.STOP, PerryState.BLOCKED):
        assert ZoneArbiter(initial_state=st, full_cubes=2).gate_closed


def test_gate_is_open_when_free_and_not_full():
    a = free_arbiter()
    a.set_zone_cubes(1)
    assert not a.gate_closed


def test_full_zone_closes_the_gate_and_denies_the_key():
    a = free_arbiter()
    a.set_zone_cubes(2)
    assert a.gate_closed
    granted, holder, _ = a.request_zone("ferb", now=10.0)
    assert not granted and holder == "perry"


# --- cola de llegada ---

def test_the_key_goes_to_the_car_that_asked_first():
    a = free_arbiter()
    a.set_state(PerryState.SCANNING)                       # Perry trabajando: los dos esperan
    assert not a.request_zone("phineas", now=10.0)[0]
    assert not a.request_zone("ferb", now=10.5)[0]
    a.set_state(PerryState.FREE)
    assert not a.request_zone("ferb", now=11.0)[0]         # pidió segundo: espera
    assert a.request_zone("phineas", now=11.2)[0]          # pidió primero: entra
    assert a.release_zone("phineas", delivered=True, color="blue", now=20.0)[0]
    a.set_state(PerryState.FREE)
    assert a.request_zone("ferb", now=21.0)[0]


def test_a_car_that_stopped_asking_loses_its_place():
    a = free_arbiter()
    a.set_state(PerryState.SCANNING)
    a.request_zone("phineas", now=10.0)                    # y después dejó de pedir (se fue)
    a.set_state(PerryState.FREE)
    assert a.request_zone("ferb", now=14.0)[0]             # 4 s > queue_ttl_s: phineas ya no cuenta


def test_cars_waiting_only_counts_recent_requests():
    a = free_arbiter()
    a.set_state(PerryState.SCANNING)
    a.request_zone("ferb", now=10.0)
    assert a.cars_waiting(now=12.0)
    assert not a.cars_waiting(now=14.0)


# --- Perry cede la llave ---

def _two_cubes():
    return Cube("azul", 15.35, -3.0, 0.0), Cube("azul", 15.35, 3.0, 0.0)


def test_perry_yields_after_one_cube_when_a_car_waits(cfg):
    a1, a2 = _two_cubes()
    arbiter = ZoneArbiter(initial_state=PerryState.STOP, full_cubes=2, queue_ttl_s=60.0)
    arbiter.request_zone("ferb")                           # ferb espera desde el principio
    cam = DummyCamera(cfg, [[a1, a2], [a2], [a2]])
    log = DummyLog()
    done = sort_loop(cfg, DummyMaestro(energized=True, parked=True), cam, log, run=True, arbiter=arbiter)
    assert done == 1
    assert arbiter.state == PerryState.FREE                # libera aunque quede un cubo: que entre ferb
    assert any("cedo la zona" in msg for msg in log.messages)


def test_perry_keeps_sorting_when_nobody_waits(cfg):
    a1, a2 = _two_cubes()
    arbiter = ZoneArbiter(initial_state=PerryState.STOP, full_cubes=2, queue_ttl_s=60.0)
    cam = DummyCamera(cfg, [[a1, a2], [a2], [a2], [], []])
    done = sort_loop(cfg, DummyMaestro(energized=True, parked=True), cam, DummyLog(), run=True, arbiter=arbiter)
    assert done == 2
