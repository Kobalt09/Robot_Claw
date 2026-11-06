"""Paso a paso con la escena cambiada (06-11): el ciclo 3 se planificó a las 11:22:45 y se aprobó a las 11:26:16.
En esos 3,5 min se movieron cubos y cajas, y Perry bajó a agarrar donde ya no había nada.
Ahora, al aprobar, vuelve a mirar: si la escena cambió, no ejecuta y planifica de nuevo.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from grasp import Cube  # noqa: E402
from sort_cubes import scene_changed, sort_loop  # noqa: E402
from test_sort_arbiter import DummyCamera, DummyLog, DummyMaestro, cfg  # noqa: E402,F401
from zone_arbiter import PerryState, ZoneArbiter  # noqa: E402

BLUE = Cube("azul", 15.35, 3.0, 0.0)
MOVED = Cube("azul", 15.35, 6.0, 0.0)


def test_scene_changed(cfg):
    assert not scene_changed(cfg, [BLUE], [Cube("azul", 15.5, 3.1, 4.0)])   # unos mm: la misma escena
    assert scene_changed(cfg, [BLUE], [MOVED])
    assert scene_changed(cfg, [BLUE], [])
    assert scene_changed(cfg, [], [BLUE])


def test_a_flickering_cube_out_of_reach_is_not_a_change(cfg):
    far = Cube("azul", 20.0, 1.8, 41.0)        # en el borde lejano: la cámara lo ve en una foto y en otra no
    assert not scene_changed(cfg, [BLUE, far], [BLUE])
    assert not scene_changed(cfg, [BLUE], [BLUE, far])


def test_approved_step_is_not_run_if_the_scene_changed_meanwhile(cfg):
    log = DummyLog()
    # 1) foto del plan, 2) foto al aprobar: el cubo ya no está, 3) nueva vuelta: zona vacía
    cam = DummyCamera(cfg, [[BLUE], [], []])
    done = sort_loop(cfg, DummyMaestro(energized=True, parked=True), cam, log, run=True,
                     approve=lambda: None, arbiter=ZoneArbiter(initial_state=PerryState.STOP))
    assert done == 0
    assert any("cambió" in msg for msg in log.messages)


def test_approved_step_runs_if_the_scene_is_the_same(cfg):
    log = DummyLog()
    cam = DummyCamera(cfg, [[BLUE], [BLUE], [], []])
    done = sort_loop(cfg, DummyMaestro(energized=True, parked=True), cam, log, run=True,
                     approve=lambda: None, arbiter=ZoneArbiter(initial_state=PerryState.STOP))
    assert done == 1
    assert not any("cambió" in msg for msg in log.messages)
