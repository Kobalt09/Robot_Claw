"""Tests: dirección de un empuje dicha en palabras (vista desde detrás del brazo, mirando la zona)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from planner import direction_words  # noqa: E402


def test_cardinal_directions():
    assert direction_words(1, 0) == "alejándose de la base"
    assert direction_words(-1, 0) == "hacia la base"
    assert direction_words(0, 1) == "hacia la izquierda"
    assert direction_words(0, -1) == "hacia la derecha"


def test_diagonals_combine_both():
    assert direction_words(0.7, -0.7) == "hacia la derecha y alejándose de la base"
    assert direction_words(-0.7, 0.7) == "hacia la izquierda y hacia la base"


def test_small_component_is_ignored():
    assert direction_words(0.2, -0.98) == "hacia la derecha"
