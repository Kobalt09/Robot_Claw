"""Descarte de cubos rojos (05-11): Perry saca de la zona los rojos que tapan un objetivo y, al terminar,
los que queden, y los apoya sobre la mesa más allá de la caja verde.

Escena real: un amarillo rodeado por 4 rojos en cruz. Antes se trababa («ninguno se puede agarrar ni
separar empujando»): Perry esquivaba los rojos pero nunca los tocaba.
"""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from grasp import Cube  # noqa: E402
from planner import decide  # noqa: E402
from reach import interp_reach  # noqa: E402
from sort_cubes import discard_pose, sort_loop  # noqa: E402
from test_sort_arbiter import DummyCamera, DummyLog, DummyMaestro, cfg  # noqa: E402,F401
from zone_arbiter import PerryState, ZoneArbiter  # noqa: E402

CFG = yaml.safe_load((Path(__file__).resolve().parent.parent / "config" / "arm.yaml").read_text(encoding="utf-8"))
# la cruz del 05-11 tal como la vio la cámara
CROSS = [Cube("rojo", 12.4, 2.5, 2.0), Cube("rojo", 16.5, 2.7, 3.0), Cube("rojo", 14.5, 4.7, 1.0),
         Cube("rojo", 14.7, 0.6, 1.0), Cube("amarillo", 14.5, 2.6, -4.0)]
YELLOW_FREE = Cube("amarillo", 15.3, -4.0, 0.0)
LONE_RED = Cube("rojo", 15.3, 4.0, 0.0)


def test_the_cross_starts_by_acting_on_a_red():
    # el amarillo no se puede agarrar: Perry trabaja sobre un rojo (lo separa empujando, porque el rojo de
    # abajo tiene el amarillo pegado detrás y ahí pegaría el cuerpo de la pinza)
    d = decide(CFG, CROSS)
    assert d.kind in ("grab", "push")
    assert d.cube.color == "rojo"
    if d.kind == "grab":
        assert d.box == "descarte" and "DESCARTAR" in d.message


def test_a_free_target_goes_before_any_red():
    d = decide(CFG, CROSS + [YELLOW_FREE])
    assert d.kind == "grab" and d.cube is YELLOW_FREE and d.box == "verde"


def test_leftover_reds_are_cleaned_when_no_target_remains():
    d = decide(CFG, [LONE_RED])
    assert d.kind == "grab" and d.cube is LONE_RED and d.box == "descarte"


def test_reds_are_left_alone_when_the_operator_only_wants_one_color():
    # «solo azul»: Perry hace lo pedido y no se pone a limpiar
    d = decide(CFG, [LONE_RED], colors=["azul"])
    assert d.kind == "none"


def test_discard_slots_use_the_taught_rows_and_do_not_repeat_in_a_row():
    s = CFG["sort"]
    a, b = discard_pose(CFG, 0), discard_pose(CFG, 1)
    assert a["base"] == b["base"] == CFG["poses"]["descarte"]["base"]
    row = interp_reach(CFG, s["discard_rs"][0], "grip")
    assert a["hombro"] == row["hombro"] + s["discard_lift_us"]
    assert a != b                                              # el segundo rojo no cae encima del primero
    assert discard_pose(CFG, len(s["discard_rs"])) == a        # cuando se llenan, vuelve a empezar


def test_sort_loop_discards_the_red_and_frees_the_zone(cfg):
    arbiter = ZoneArbiter(initial_state=PerryState.STOP)
    log = DummyLog()
    cam = DummyCamera(cfg, [[LONE_RED], [], []])
    done = sort_loop(cfg, DummyMaestro(energized=True, parked=True), cam, log, run=True, arbiter=arbiter)
    assert done == 0                                  # descartar no cuenta como clasificar
    assert arbiter.sorted_total == 0
    assert arbiter.state == PerryState.FREE
    assert any("descart" in msg.lower() for msg in log.messages)


# --- el cuerpo de la pinza pega en el cubo de atrás (05-11) ---

def test_a_cube_with_another_right_behind_is_not_grabbed_first():
    from grasp import GraspCfg, blocked_behind
    g = GraspCfg(**CFG["grasp"])
    near, behind = Cube("rojo", 12.1, 2.4, 9.25), Cube("amarillo", 14.5, 2.6, -4.0)   # 0,5 cm de luz
    side = Cube("rojo", 12.1, 4.4, 0.0)                                                # al costado, no atrás
    assert blocked_behind(near, [near, behind], g)
    assert not blocked_behind(behind, [near, behind], g)       # el de adelante no le molesta al de atrás
    assert not blocked_behind(near, [near, side], g)


def test_the_red_cross_is_solved_end_to_end():
    cubes = list(CROSS)
    for _ in range(14):
        d = decide(CFG, cubes)
        if d.kind == "grab":
            cubes = [k for k in cubes if k is not d.cube]
        elif d.kind == "push":
            cubes = list(d.plan.predicted)
        else:
            break
    assert d.kind == "none" and not cubes       # se agarró el amarillo y se descartaron todos los rojos
