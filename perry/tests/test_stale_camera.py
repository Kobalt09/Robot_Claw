"""Cuadro congelado (06-11): el ciclo planificó 3 veces el mismo empuje con 3 fotos IDÉNTICAS (diferencia 0,0)
mientras el brazo movía cubos y la vista en vivo seguía bien. El ciclo leía una cámara cerrada o sin cuadros
nuevos, y la captura seguía devolviendo el último cuadro como bueno.
"""
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
import audit_web  # noqa: E402
from codigo_python.camara_stream import CapturaCamara  # noqa: E402


def capture(age_s, running=True):
    """Una CapturaCamara sin dispositivo, con un cuadro de hace `age_s` segundos."""
    cam = CapturaCamara.__new__(CapturaCamara)
    cam.usar_hilo, cam.corriendo, cam.max_edad_s = True, running, 1.0
    cam.bloqueo = threading.Lock()
    cam.frame_actual = np.zeros((4, 4, 3), np.uint8)
    cam.t_frame = time.time() - age_s
    return cam


def test_a_fresh_frame_is_returned():
    ok, f = capture(0.1).leer_frame()
    assert ok and f is not None


def test_an_old_frame_is_not_passed_off_as_new():
    ok, f = capture(5.0).leer_frame()
    assert not ok and f is None


def test_a_released_camera_gives_no_frame():
    ok, _ = capture(0.1, running=False).leer_frame()
    assert not ok


def test_the_cycle_always_reads_the_panel_current_camera():
    class Fake:
        def __init__(self, name):
            self.name = name
    proxy = audit_web.CurrentCamera(wait_s=0.2)
    audit_web.S.cam = Fake("vieja")
    assert proxy.name == "vieja"
    audit_web.S.cam = Fake("nueva")          # el panel reabrió la cámara
    assert proxy.name == "nueva"
    audit_web.S.cam = None                   # reabriendo: espera y, si no vuelve, avisa
    with pytest.raises(RuntimeError):
        proxy.name


def test_the_camera_is_reopened_only_when_its_settings_change():
    a = {"camera": {"index": 0, "corners_px": [[1, 2]]}, "grasp": {"opening": 3.2}}
    b = {"camera": {"index": 0, "corners_px": [[1, 2]]}, "grasp": {"opening": 3.6}}
    c = {"camera": {"index": 1, "corners_px": [[1, 2]]}, "grasp": {"opening": 3.2}}
    assert not audit_web.camera_changed(a, b)     # otra corrida, otra pinza: misma cámara
    assert audit_web.camera_changed(a, c)
