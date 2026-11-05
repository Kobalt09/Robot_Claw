"""Qué índices de cámara prueba el panel (05-11).

En la notebook de Cristian la cenital no estaba en 0 ni en 1: el panel abría la cámara integrada
(que abre sin error) y nunca probaba otra. Ahora cada PC puede fijar la suya con PERRY_CAMERA
sin tocar arm.yaml (que es compartido), y sin la variable se prueban más índices.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vision import camera_candidates  # noqa: E402

CAM = {"index": 1, "max_index": 4}


def test_without_env_starts_with_config_index_then_the_rest():
    assert camera_candidates(CAM, {}) == [1, 0, 2, 3]


def test_env_fixes_a_single_index_no_fallback():
    # con la variable puesta no se cae a otra cámara en silencio: si no abre, error
    assert camera_candidates(CAM, {"PERRY_CAMERA": "2"}) == [2]


def test_env_with_spaces_is_accepted():
    assert camera_candidates(CAM, {"PERRY_CAMERA": " 3 "}) == [3]


def test_empty_env_is_ignored():
    assert camera_candidates(CAM, {"PERRY_CAMERA": ""}) == [1, 0, 2, 3]


def test_invalid_env_is_an_error():
    with pytest.raises(ValueError, match="PERRY_CAMERA"):
        camera_candidates(CAM, {"PERRY_CAMERA": "webcam"})


def test_config_index_beyond_max_is_still_tried_first():
    assert camera_candidates({"index": 6, "max_index": 2}, {}) == [6, 0, 1]
