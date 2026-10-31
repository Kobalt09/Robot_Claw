"""Tests: resumen de la prueba de precisión (error del brazo por punto y total)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from precision import summarize  # noqa: E402


def test_perfect_run():
    s = summarize([((16, 0), (16, 0)), ((13, 0), (13, 0))], threshold=0.4)
    assert s["rms"] == 0 and s["ok"]


def test_errors_mean_rms_and_worst():
    # pedido -> medido
    pairs = [((16, 0), (16.3, 0.0)), ((13, 0), (13.0, -0.4))]
    s = summarize(pairs, threshold=0.4)
    assert s["mean_dx"] == pytest.approx(0.15)
    assert s["mean_dy"] == pytest.approx(-0.2)
    assert s["rms"] == pytest.approx(((0.3 ** 2 + 0.4 ** 2) / 2) ** 0.5)
    assert s["worst"]["target"] == (13, 0) and s["worst"]["error"] == pytest.approx(0.4)
    assert s["ok"]                                 # rms 0.35 <= 0.4


def test_over_threshold_flags_recalibration():
    s = summarize([((16, 0), (16.8, 0.0))], threshold=0.4)
    assert not s["ok"]


def test_missing_measurement_counts_as_failure():
    s = summarize([((16, 0), None), ((13, 0), (13.1, 0.0))], threshold=0.4)
    assert s["missing"] == 1 and not s["ok"]


def test_squeeze_error_combines_two_axes():
    from precision import squeeze_error
    # cerrar en 0°: el cubo se corrió +0.3 en X; cerrar en 90°: se corrió -0.2 en Y
    before = (16.0, 0.0)
    after_a = (16.3, 0.05)      # algo de ruido en el eje que no se midió
    after_b = (16.32, -0.2)
    dx, dy = squeeze_error(before, after_a, 0.0, after_a, after_b, 90.0)
    assert dx == pytest.approx(0.3) and dy == pytest.approx(-0.25)


def test_squeeze_error_projects_on_rotated_axes():
    from precision import squeeze_error
    import math
    t = math.radians(30)
    e = (0.4 * math.cos(t), 0.4 * math.sin(t))     # error real de 4 mm a 30°
    a1 = (16 + e[0], e[1])                          # cerrando a 30° se ve todo el error
    dx, dy = squeeze_error((16, 0), a1, 30.0, a1, a1, 120.0)   # a 120° no se mueve
    assert (dx, dy) == pytest.approx(e)
