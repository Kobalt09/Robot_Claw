"""Tests: esperar a que la imagen deje de cambiar antes de detectar (el brazo puede estar cruzando)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vision import wait_still  # noqa: E402


def frames(seq):
    it = iter(seq)
    return lambda: next(it)


def still(v):
    return np.full((40, 40, 3), v, np.uint8)


def test_returns_first_frame_of_a_still_pair():
    moving = [still(0), still(200), still(50), still(50), still(50)]
    f, ok = wait_still(frames(moving), pause=0.0, tol=5.0, timeout=10)
    assert ok and f.mean() == 50


def test_gives_up_after_timeout_but_returns_last_frame():
    import itertools
    alternating = itertools.cycle([still(0), still(200)])
    f, ok = wait_still(lambda: next(alternating), pause=0.0, tol=5.0, timeout=0.05)
    assert not ok and f is not None
