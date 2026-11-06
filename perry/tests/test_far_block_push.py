"""Bloque en el borde lejano (06-11, corrida 2026-11-06_11-33-21): «Hay cubos, pero ninguno se puede agarrar ni
separar empujando». Empujar el bloque de costado dejaba todos los cubos bien, pero el azul ya fuera de alcance
pasaba de 20,09 a 20,11 cm y la regla «un cubo ya fuera no puede quedar más lejos» lo rechazaba por 2 mm
(menos que el ruido de la cámara). Ahora hay una tolerancia, y esos cubos no pueden salir de la zona.
"""
import sys
from math import hypot
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from grasp import Cube  # noqa: E402
from planner import decide, in_zone  # noqa: E402

CFG = yaml.safe_load((Path(__file__).resolve().parent.parent / "config" / "arm.yaml").read_text(encoding="utf-8"))
BLOCK = [Cube("azul", 18.68, 3.44, 40.5), Cube("azul", 17.36, 5.2, 11.8), Cube("azul", 20.01, 1.78, 40.6),
         Cube("rojo", 14.83, 4.49, 40.7), Cube("amarillo", 17.49, 1.59, -44.3), Cube("amarillo", 16.11, 2.91, 40.7)]


def test_far_block_is_pushed_instead_of_giving_up():
    d = decide(CFG, BLOCK, ignored=[(20.01, 1.78)])
    assert d.kind == "push", d.message


def test_pushed_cubes_never_leave_the_zone():
    d = decide(CFG, BLOCK, ignored=[(20.01, 1.78)])
    tol = CFG["grasp"]["push_far_tol"]
    for before, after in zip(BLOCK, d.plan.predicted):
        assert in_zone(CFG, after), (before, after)
        assert hypot(after.x, after.y) <= max(hypot(before.x, before.y) + tol, CFG["reach"]["max_r"])
