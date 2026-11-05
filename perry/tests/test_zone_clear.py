"""Detector de «objeto grande» dentro de la zona azul (la pala de un carro, o el brazo).

Se prueba con fotos REALES de la cámara cenital (tests/images/, 31-10 y 02-11), con la calibración
actual de arm.yaml. Los carros no llevan ArUco: Perry los reconoce porque son mucho más grandes que un cubo.
"""
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from vision import zone_blobs_cm2, zone_is_clear  # noqa: E402

CFG = yaml.safe_load((HERE.parent / "config" / "arm.yaml").read_text(encoding="utf-8"))
# Las fotos de tests/images se sacaron el 31-10 con esta calibración: la de hoy en arm.yaml cambia cada vez
# que mueven la cámara, y el rectángulo de la zona ya no caería sobre ellas.
IMAGES_CORNERS_PX = [[239.0, 164.0], [399.0, 156.0], [403.0, 251.0], [244.0, 260.0]]
CFG["camera"]["corners_px"] = IMAGES_CORNERS_PX
IMAGES = HERE / "images"


def load(name):
    return cv2.imdecode(np.frombuffer((IMAGES / name).read_bytes(), np.uint8), cv2.IMREAD_COLOR)


@pytest.mark.parametrize("name", ["brazo_estacionado_zona_vacia.jpg", "brazo_estacionado_cubo_amarillo.jpg",
                                  "cubo_azul_en_zona.jpg"])
def test_cubes_and_the_parked_arm_do_not_count_as_a_big_object(name):
    assert zone_is_clear(load(name), CFG), f"{name}: manchas {zone_blobs_cm2(load(name), CFG)}"


def test_the_arm_over_the_zone_is_a_big_object():
    assert not zone_is_clear(load("brazo_sobre_zona.jpg"), CFG)


def test_a_single_cube_is_measured_close_to_its_real_area():
    blobs = zone_blobs_cm2(load("cubo_azul_en_zona.jpg"), CFG)
    cube = CFG["grasp"]["cube"] ** 2
    assert any(0.5 * cube <= a <= 2.0 * cube for a in blobs), blobs


def test_a_dark_scoop_entering_the_zone_is_a_big_object():
    # pala sintética: un rectángulo oscuro de ~6 x 4 cm metido en la zona vacía
    img = load("brazo_estacionado_zona_vacia.jpg")
    Hinv = cv2.getPerspectiveTransform(np.float32(CFG["camera"]["corners_cm"]), np.float32(CFG["camera"]["corners_px"]))
    scoop_cm = np.float32([[19.0, -3.0], [19.0, 3.0], [15.0, 3.0], [15.0, -3.0]]).reshape(-1, 1, 2)
    cv2.fillPoly(img, [np.int32(cv2.perspectiveTransform(scoop_cm, Hinv).reshape(-1, 2))], (30, 30, 30))
    assert not zone_is_clear(img, CFG)


def test_a_row_of_four_touching_cubes_is_not_a_big_object():
    # los cubos pegados (fila de 4) no deben confundirse con un carro
    img = load("brazo_estacionado_zona_vacia.jpg")
    Hinv = cv2.getPerspectiveTransform(np.float32(CFG["camera"]["corners_cm"]), np.float32(CFG["camera"]["corners_px"]))
    g = CFG["grasp"]["cube"]
    row_cm = np.float32([[16.0, -2 * g], [16.0, 2 * g], [16.0 - g, 2 * g], [16.0 - g, -2 * g]]).reshape(-1, 1, 2)
    cv2.fillPoly(img, [np.int32(cv2.perspectiveTransform(row_cm, Hinv).reshape(-1, 2))], (0, 200, 230))
    assert zone_is_clear(img, CFG), zone_blobs_cm2(img, CFG)
