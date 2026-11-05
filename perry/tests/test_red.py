"""Cubos rojos (05-11): los carros a veces los traen por accidente. Perry los ve, los esquiva y no los toma,
y no dejan la zona trabada: se avisa para retirarlos a mano.

Antes eran invisibles: el planificador podía bajar un dedo sobre un rojo y la pinza quedaba encima del cubo.
"""
import sys
from pathlib import Path

import cv2
import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import audit_web  # noqa: E402
from audit_web import S  # noqa: E402
from grasp import Cube  # noqa: E402
from planner import decide, sortable  # noqa: E402
from sort_cubes import sort_loop  # noqa: E402
from test_sort_arbiter import DummyCamera, DummyLog, DummyMaestro, cfg  # noqa: E402,F401
from vision import TopCamera  # noqa: E402
from zone_arbiter import PerryState, ZoneArbiter  # noqa: E402

CFG = yaml.safe_load((HERE.parent / "config" / "arm.yaml").read_text(encoding="utf-8"))
BLUE = Cube("azul", 15.35, 3.0, 0.0)
RED = Cube("rojo", 15.35, -3.0, 0.0)
# foto real del 05-11: 4 rojos (3 pegados) y 1 azul en la zona, con la calibración de ese momento
RED_IMAGE = HERE / "images" / "rojos_en_zona_05-11.jpg"
RED_IMAGE_CORNERS_PX = [[245.0, 137.0], [406.0, 128.0], [409.0, 223.0], [251.0, 232.0]]


def test_red_is_seen_by_the_camera():
    c = dict(CFG)
    c["camera"] = dict(CFG["camera"], corners_px=RED_IMAGE_CORNERS_PX)
    cam = TopCamera.__new__(TopCamera)          # sin abrir la cámara: solo la detección
    TopCamera._setup_detection(cam, c)
    frame = cv2.imdecode(np.frombuffer(RED_IMAGE.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
    cubes, _ = cam.find_cubes(frame)
    colors = sorted(k.color for k in cubes)
    assert colors.count("rojo") == 4, colors
    assert colors.count("azul") == 1, colors


def test_red_is_not_for_sorting():
    assert not sortable(CFG, RED)
    assert sortable(CFG, BLUE)


def test_red_is_an_obstacle_never_a_target():
    d = decide(CFG, [RED, BLUE])
    assert d.kind == "grab" and d.cube.color == "azul"
    d = decide(CFG, [RED])            # sin objetivos, el rojo se descarta (no va a ninguna caja)
    assert d.kind == "grab" and d.box == "descarte"
    assert not d.unreachable          # un rojo no se reporta como "fuera de alcance" de los que hay que clasificar


def test_a_red_left_in_the_zone_does_not_block_it(cfg):
    arbiter = ZoneArbiter(initial_state=PerryState.STOP)
    log = DummyLog()
    cam = DummyCamera(cfg, [[BLUE, RED], [RED], [RED]])
    done = sort_loop(cfg, DummyMaestro(energized=True, parked=True), cam, log, run=True, arbiter=arbiter)
    assert done == 1
    assert arbiter.state == PerryState.FREE
    assert arbiter.snapshot()["zone_cubes"] == 0          # tampoco cuenta para "zona llena"
    assert any("rojo" in msg and "descarte" in msg for msg in log.messages)


def test_blocked_zone_reopens_with_only_red_cubes_left():
    S.cfg = CFG
    empty = cv2.imdecode(np.frombuffer((HERE / "images" / "brazo_estacionado_zona_vacia.jpg").read_bytes(),
                                       np.uint8), cv2.IMREAD_COLOR)
    S.cfg = dict(CFG, camera=dict(CFG["camera"], corners_px=[[239.0, 164.0], [399.0, 156.0], [403.0, 251.0],
                                                              [244.0, 260.0]]))
    assert audit_web.blocked_can_reopen(empty, cubes=[RED])
    assert not audit_web.blocked_can_reopen(empty, cubes=[BLUE])
