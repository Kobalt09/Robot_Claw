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
