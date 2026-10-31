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


@pytest.mark.parametrize("path", SCENES, ids=[p.stem for p in SCENES])
def test_push_keeps_moved_cubes_away_from_both_reach_limits(path):
    # un empuje en cadena corre los cubos unos mm más de lo previsto: lo que se mueva debe quedar a
    # push_margin_r de AMBOS bordes del alcance (pi_2026-10-31_corrida1_c4: previsto 12,2, real 11,7)
    s = json.loads(path.read_text(encoding="utf-8"))
    cubes = scene_cubes(s["cubes"])
    d = decide(CFG, cubes, to=s.get("to"))
    if d.kind != "push":
        pytest.skip("no empuja")
    m = CFG["sort"]["push_margin_r"]
    r_min = min(row["r"] for row in CFG["reach"]["rows"]) + m
    r_max = CFG["reach"]["max_r"] - m
    for before, after in zip(cubes, d.plan.predicted):
        if (before.x, before.y) != (after.x, after.y):
            r = (after.x ** 2 + after.y ** 2) ** 0.5
            assert r_min <= r <= r_max, f"{path.stem}: cubo empujado a r = {r:.1f} cm (permitido {r_min:.1f}–{r_max:.1f})"
