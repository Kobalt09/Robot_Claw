"""Cierre en línea con el brazo (06-11): a más de ~14 cm del eje, cerrar los dedos a lo largo de la
línea brazo-cubo fallaba siempre (4 de 4: el dedo de afuera bajaba sobre la cara de arriba y el cubo
salía empujado hacia afuera). Cerrando de costado (≥ 30° de esa línea) no falló ninguno.

Escenas reales de la corrida 2026-11-06_10-33-03 (ciclos 4 y 5, el mismo azul).
"""
import sys
from math import hypot
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from grasp import Cube, GraspCfg, axis_clearance, radial_ok, relative_giro  # noqa: E402
from planner import decide  # noqa: E402

CFG = yaml.safe_load((Path(__file__).resolve().parent.parent / "config" / "arm.yaml").read_text(encoding="utf-8"))
G = GraspCfg(**CFG["grasp"])
CYCLE4 = [Cube("azul", 15.33, -5.12, 24.7), Cube("azul", 17.67, -4.64, -15.5), Cube("azul", 16.61, -0.82, 5.9),
          Cube("azul", 16.44, 1.15, 8.3), Cube("rojo", 14.47, -3.26, 22.4)]
CYCLE5 = [Cube("azul", 15.28, -5.12, 26.0), Cube("azul", 17.66, -4.63, -16.8), Cube("rojo", 14.45, -3.26, 25.3),
          Cube("azul", 17.65, -1.09, -20.9), Cube("azul", 17.48, 1.54, 17.6)]


def off_radial(c, d):
    """Grados entre la dirección de cierre y la línea brazo-cubo (0 = en línea, 90 = de costado)."""
    return 90.0 - abs(relative_giro(c, d))


def test_far_cube_cannot_close_along_the_arm():
    c = Cube("azul", 16.44, 1.15, 8.3)
    radial = next(d for d in (c.angle, c.angle + 90) if off_radial(c, d) < 30)
    assert not radial_ok(c, radial, G)
    assert axis_clearance(c, [c], radial, G) < 0          # aunque no tenga vecinos
    assert axis_clearance(c, [c], radial + 90, G) >= 0    # de costado sí


def test_near_cube_may_still_close_along_the_arm():
    # el 05-11 un rojo a 12,6 cm se agarró bien cerrando en línea con el brazo
    c = Cube("rojo", 12.08, 3.78, 3.9)
    assert hypot(c.x, c.y) < G.radial_min_r
    assert all(radial_ok(c, d, G) for d in (c.angle, c.angle + 90))


def test_real_scenes_never_grab_closing_along_the_arm():
    for cubes in (CYCLE4, CYCLE5):
        d = decide(CFG, cubes)
        assert d.kind in ("grab", "push"), d.message
        if d.kind == "grab" and hypot(d.cube.x, d.cube.y) > G.radial_min_r:
            assert off_radial(d.cube, d.grasp_dir) >= G.radial_min_deg, d.message
