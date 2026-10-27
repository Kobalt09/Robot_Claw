"""Tests: separar manchas de cubos del mismo color pegados.

Los rastrillos los dejan en filas prolijas, pero después de un empuje o un agarre fallido quedan
escalonados, en L o girados distinto. Se cuenta por ÁREA y se reparten los puntos con k-means.
"""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vision import split_region  # noqa: E402

S = 1.9      # lado del cubo (cm)
STEP = 0.1   # resolución del muestreo (cm), como ~1 píxel de la cenital


def square_pts(cx, cy, ang=0.0, side=S):
    """Puntos del interior de un cubo visto desde arriba (en cm)."""
    t = math.radians(ang)
    u, v = np.array([math.cos(t), math.sin(t)]), np.array([-math.sin(t), math.cos(t)])
    k = np.arange(-side / 2 + STEP / 2, side / 2, STEP)
    return np.array([[cx, cy] + a * u + b * v for a in k for b in k], np.float32)


def blob(*cubes):
    pts = np.vstack([square_pts(*c) for c in cubes])
    return pts, len(pts) * STEP * STEP


def found(out):
    return sorted((x, y) for x, y, _ in out)


def near(a, b, tol=0.35):
    return len(a) == len(b) and all(math.hypot(p[0] - q[0], p[1] - q[1]) < tol for p, q in zip(sorted(a), sorted(b)))


def test_single_cube():
    out = split_region(*blob((15, 0)), S)
    assert near(found(out), [(15, 0)])


def test_row_of_two():
    out = split_region(*blob((15, 0), (15 + S, 0)), S)
    assert near(found(out), [(15, 0), (15 + S, 0)])


def test_staggered_pair_after_a_push():
    # como en la foto: el segundo cubo quedó corrido medio cubo
    out = split_region(*blob((15, 0), (15 + S, S / 2)), S)
    assert near(found(out), [(15, 0), (15 + S, S / 2)])


def test_l_shape_of_three():
    out = split_region(*blob((15, 0), (15 + S, 0), (15, S)), S)
    assert near(found(out), [(15, 0), (15 + S, 0), (15, S)])


def test_2x2_block():
    cubes = [(15, 0), (15 + S, 0), (15, S), (15 + S, S)]
    assert near(found(split_region(*blob(*cubes), S)), cubes)


def test_touching_cubes_with_different_rotation():
    out = split_region(*blob((15, 0, 0), (15 + S * 1.1, 0.3, 30)), S)
    assert len(out) == 2
    angles = sorted(a for _, _, a in out)
    assert angles[0] == pytest.approx(0, abs=5) and angles[1] == pytest.approx(30, abs=5)


def test_eroded_row_still_two():
    # la segmentación se come ~10 % del borde
    pts, area = blob((15, 0), (15 + S, 0))
    assert len(split_region(pts, area * 0.8, S)) == 2


def test_rotated_row_keeps_rotation():
    t = math.radians(30)
    cubes = [(15 + i * S * math.cos(t), i * S * math.sin(t), 30) for i in range(3)]
    out = split_region(*blob(*cubes), S)
    assert near(found(out), [(x, y) for x, y, _ in cubes])
    assert all(a == pytest.approx(30, abs=5) for _, _, a in out)
