"""Elegir desde el panel qué color agarrar (02-11): los demás cubos quedan en la mesa como obstáculos."""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from audit_web import parse_start  # noqa: E402
from grasp import Cube  # noqa: E402
from planner import decide  # noqa: E402
from sort_cubes import sort_loop  # noqa: E402
from test_sort_arbiter import DummyCamera, DummyLog, DummyMaestro, cfg  # noqa: E402,F401
from zone_arbiter import PerryState, ZoneArbiter  # noqa: E402

CFG = yaml.safe_load((Path(__file__).resolve().parent.parent / "config" / "arm.yaml").read_text(encoding="utf-8"))
BLUE = Cube("azul", 15.35, 3.0, 0.0)
YELLOW = Cube("amarillo", 15.35, -3.0, 0.0)


def test_only_the_chosen_color_is_grabbed():
    d = decide(CFG, [YELLOW, BLUE], colors=["azul"])
    assert d.kind == "grab" and d.cube.color == "azul"
    d = decide(CFG, [YELLOW, BLUE], colors=["amarillo"])
    assert d.kind == "grab" and d.cube.color == "amarillo"


def test_nothing_to_do_when_only_other_colors_remain():
    d = decide(CFG, [YELLOW], colors=["azul"])
    assert d.kind == "none"
    assert "azul" in d.message


def test_without_a_choice_every_color_counts():
    assert decide(CFG, [YELLOW]).kind == "grab"


def test_sort_loop_leaves_other_colors_and_frees_the_zone(cfg):
    arbiter = ZoneArbiter(initial_state=PerryState.STOP)
    cam = DummyCamera(cfg, [[BLUE, YELLOW], [YELLOW], [YELLOW]])
    log = DummyLog()
    done = sort_loop(cfg, DummyMaestro(energized=True, parked=True), cam, log, run=True, arbiter=arbiter,
                     colors=["azul"])
    assert done == 1
    # el amarillo quedó por elección del operador, no porque la zona esté trabada
    assert arbiter.state == PerryState.FREE


def test_panel_start_body_carries_mode_and_color():
    assert parse_start("run|azul") == ("run", ["azul"])
    assert parse_start("step|amarillo") == ("step", ["amarillo"])
    assert parse_start("run|") == ("run", None)
    assert parse_start("look") == ("look", None)
