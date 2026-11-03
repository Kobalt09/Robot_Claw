"""ASENTANDO: después de que un carro devuelve la llave, Perry no mueve el brazo hasta que la cámara
confirma la zona despejada (sin objeto grande), la escena quieta y pasó un tiempo mínimo.
Ver docs/perry_zona_estados.md, sección 4.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from settle import Settler  # noqa: E402

T0 = 100.0


def make():
    return Settler(T0, min_s=2.0, max_s=10.0)


def test_waits_the_minimum_time_even_if_the_zone_looks_clear():
    s = make()
    assert s.update(T0 + 0.5, clear=True, still=True) == "wait"
    assert s.update(T0 + 1.9, clear=True, still=True) == "wait"


def test_goes_after_the_minimum_when_clear_and_still():
    assert make().update(T0 + 2.0, clear=True, still=True) == "go"


def test_waits_while_a_big_object_is_in_the_zone():
    s = make()
    assert s.update(T0 + 3.0, clear=False, still=True) == "wait"
    assert "objeto grande" in s.reason


def test_waits_while_the_scene_moves():
    s = make()
    assert s.update(T0 + 3.0, clear=True, still=False) == "wait"
    assert "movimiento" in s.reason


def test_blocks_if_the_zone_never_clears():
    # el carro quedó trabado con la pala adentro: cerrar la zona, no bajar el brazo
    s = make()
    assert s.update(T0 + 9.9, clear=False, still=True) == "wait"
    assert s.update(T0 + 10.0, clear=False, still=True) == "blocked"


def test_once_decided_the_answer_does_not_change():
    s = make()
    assert s.update(T0 + 2.5, clear=True, still=True) == "go"
    assert s.update(T0 + 11.0, clear=False, still=False) == "go"
