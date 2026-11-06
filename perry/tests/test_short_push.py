"""Montón en el borde lejano (06-11, corrida 2026-11-06_11-51-26): 7 cubos entre 17 y 20 cm, ninguno agarrable.
Con el empuje de 3,8 cm todos los planes sacaban algún cubo del alcance: «NADA QUE HACER». Con 3 cm o menos sí
había. Ahora, solo si 3,8 no da nada, se prueban empujes más cortos (sort.push_fallback_cm).
"""
import sys
from math import hypot
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from grasp import Cube  # noqa: E402
from planner import decide, in_zone  # noqa: E402

CFG = yaml.safe_load((Path(__file__).resolve().parent.parent / "config" / "arm.yaml").read_text(encoding="utf-8"))
PILE = [Cube("rojo", 14.98, 1.13, -25.0), Cube("azul", 18.39, 3.85, 32.6), Cube("azul", 17.29, 5.27, 9.8),
        Cube("azul", 20.21, 1.57, -43.0), Cube("azul", 19.12, 2.59, 40.6), Cube("amarillo", 17.04, 0.82, -22.9),
        Cube("amarillo", 18.72, -0.12, -22.9)]
OUT = [(20.21, 1.57)]   # fuera de alcance: ya ignorado


def test_far_pile_gets_a_shorter_push():
    d = decide(CFG, PILE, ignored=OUT)
    assert d.kind == "push", d.message
    assert d.plan.length < CFG["grasp"]["push"]
    assert f"{d.plan.length:.1f} cm" in d.message
    for p in d.plan.predicted:
        assert in_zone(CFG, p)


def test_normal_blocks_still_use_the_long_push():
    # un bloque 2x2 en el medio de la zona: el empuje de siempre (separa la fila entera)
    block = [Cube("azul", 15.0, 1.0, 0), Cube("azul", 15.0, -1.0, 0), Cube("azul", 17.0, 1.0, 0), Cube("azul", 17.0, -1.0, 0)]
    d = decide(CFG, block)
    if d.kind == "push":
        assert d.plan.length == CFG["grasp"]["push"]
