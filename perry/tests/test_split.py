"""Tests: separar manchas de cubos del mismo color pegados (los deja así el rastrillo)."""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vision import split_blob  # noqa: E402

S = 1.9  # lado del cubo (cm)


def rect_points(cx, cy, w, h, ang):
    """Contorno (en cm) de un rectángulo w x h centrado en (cx, cy) y girado ang grados."""
    t = math.radians(ang)
    u, v = np.array([math.cos(t), math.sin(t)]), np.array([-math.sin(t), math.cos(t)])
    pts = []
    for i in range(41):  # muestreo denso del borde, como un contorno real
        f = i / 40
        pts += [u * (f - 0.5) * w + v * h / 2, u * w / 2 + v * (f - 0.5) * h,
                u * (0.5 - f) * w - v * h / 2, -u * w / 2 + v * (0.5 - f) * h]
    return np.float32([p + (cx, cy) for p in pts])


def centers(blobs):
    return sorted((x, y) for x, y, _ in blobs)


def same(a, b, tol=0.05):
    return len(a) == len(b) and all(abs(p[0] - q[0]) < tol and abs(p[1] - q[1]) < tol for p, q in zip(a, b))


def test_single_cube_stays_single():
    out = split_blob(rect_points(15, 0, S, S, 0), S)
    assert same(centers(out), [(15.0, 0.0)])


def test_two_cubes_in_a_row_are_split():
    out = split_blob(rect_points(15, 0, 2 * S, S, 0), S)
    assert same(centers(out), [(15 - S / 2, 0.0), (15 + S / 2, 0.0)])


def test_three_in_a_row_rotated():
    out = split_blob(rect_points(15, 2, 3 * S, S, 30), S)
    assert len(out) == 3
    xs = sorted(x for x, _, _ in out)
    assert xs[1] == pytest.approx(15, abs=0.1)
    for _, _, ang in out:  # todos con el ángulo de la fila (módulo 90)
        assert (ang - 30) % 90 == pytest.approx(0, abs=1) or (ang - 30) % 90 == pytest.approx(90, abs=1)


def test_2x2_block_gives_four_cubes():
    out = split_blob(rect_points(15, 0, 2 * S, 2 * S, 0), S)
    h = S / 2
    assert same(centers(out), [(15 - h, -h), (15 - h, h), (15 + h, -h), (15 + h, h)])


def test_slightly_small_blob_still_counts_as_cubes():
    # la segmentación suele comerse un poco del borde
    out = split_blob(rect_points(15, 0, 2 * S - 0.4, S - 0.3, 0), S)
    assert len(out) == 2
