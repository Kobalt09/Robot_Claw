"""Escenas reales guardadas (tests/scenes/*.json): el planificador actual debe decidir lo esperado.

Cada escena sale de un ciclo real con: py replay.py guardar logs/<corrida> <ciclo> <grab|push|none>
Así cada falla vista en la mesa queda como test permanente.
"""
import json
import sys
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from replay import scene_cubes  # noqa: E402
from planner import decide  # noqa: E402

CFG = yaml.safe_load((HERE.parent / "config" / "arm.yaml").read_text(encoding="utf-8"))
SCENES = sorted((HERE / "scenes").glob("*.json"))


@pytest.mark.parametrize("path", SCENES, ids=[p.stem for p in SCENES])
def test_scene(path):
    s = json.loads(path.read_text(encoding="utf-8"))
    d = decide(CFG, scene_cubes(s["cubes"]), to=s.get("to"))
    assert d.kind == s["expect"], f"{path.stem}: {s.get('note', '')} -> {d.message}"
    if s.get("expect_color") and d.cube is not None:
        assert d.cube.color == s["expect_color"]
