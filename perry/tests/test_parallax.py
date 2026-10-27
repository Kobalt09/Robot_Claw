"""Tests: corrección de paralaje. La cámara ve la cara de ARRIBA del cubo (1,9 cm sobre la mesa),
así que todo cubo aparece corrido hacia afuera del punto que está justo debajo de la cámara."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vision import parallax_correct  # noqa: E402


def test_point_under_the_camera_does_not_move():
    assert parallax_correct(10.0, 2.0, (10.0, 2.0), 70.0, 1.9) == pytest.approx((10.0, 2.0))


def test_far_point_is_pulled_toward_the_nadir():
    # 10 cm del punto bajo la cámara, cubo de 1,9 cm, cámara a 70 cm: se acerca 10·1,9/70 = 0,27 cm
    x, y = parallax_correct(25.0, 0.0, (15.0, 0.0), 70.0, 1.9)
    assert x == pytest.approx(25.0 - 10.0 * 1.9 / 70.0)
    assert y == pytest.approx(0.0)


def test_correction_is_radial_from_the_nadir():
    x, y = parallax_correct(18.0, 6.0, (15.0, 2.0), 70.0, 1.9)
    k = 1 - 1.9 / 70.0
    assert (x, y) == pytest.approx((15.0 + 3.0 * k, 2.0 + 4.0 * k))
