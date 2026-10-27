"""Visión de Perry: encontrar cubos en la zona con la cámara cenital.

Usa el detector de colores del equipo (codigo_python/detector_colores.py) y le agrega:
- homografía píxel -> cm con las 4 esquinas del rectángulo de la zona (arm.yaml: camera);
- filtro de zona: solo cuentan los cubos dentro del rectángulo (descarta cinta, contenedores);
- ángulo del cubo visto desde arriba, para girar la pinza.

Todo número vive en arm.yaml. Si mueven la cámara: py calibrate_camera.py
"""
import sys
import time
from dataclasses import dataclass
from math import atan2, degrees
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from codigo_python.detector_colores import DetectorColores  # noqa: E402
from codigo_python.camara_stream import CapturaCamara  # noqa: E402


@dataclass
class Cube:
    color: str
    x: float          # cm, hacia la zona
    y: float          # cm, a la izquierda
    angle: float      # grados en [-45, 45): giro del cubo visto desde arriba
    area: float       # píxeles


class TopCamera:
    """Cámara cenital con la homografía de arm.yaml. Úsala con `with`."""

    def __init__(self, cfg):
        c = cfg["camera"]
        self.cfg = c
        self.H = cv2.getPerspectiveTransform(np.float32(c["corners_px"]), np.float32(c["corners_cm"]))
        self.det = DetectorColores(area_minima=c["min_area_px"])
        self.det.rangos_colores.clear()
        for name, ranges in c["colors"].items():
            self.det.configurar_color(name, [(np.array(lo, np.uint8), np.array(hi, np.uint8)) for lo, hi in ranges])
        self.cam = CapturaCamara(indice_camara=c["index"])
        time.sleep(c["warmup_s"])

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cam.liberar()

    def px_to_cm(self, u, v):
        p = self.H @ [u, v, 1.0]
        return p[0] / p[2], p[1] / p[2]

    def frame(self):
        ok, f = self.cam.leer_frame()
        if not ok:
            raise RuntimeError("la cámara cenital no entrega imagen")
        return f

    def find_cubes(self, frame=None):
        """Cubos dentro de la zona, el más grande primero. Devuelve (cubos, imagen anotada)."""
        f = self.frame() if frame is None else frame
        z = self.cfg["zone"]
        cubes = []
        detections = self.det.procesar_frame(f)
        for d in detections:
            x, y = self.px_to_cm(*d.centroide)
            if not (z["x_min"] <= x <= z["x_max"] and abs(y) <= z["y_abs"]):
                continue
            # ángulo con una arista del rectángulo mínimo, pasada a cm (sin perspectiva)
            box = cv2.boxPoints(cv2.minAreaRect(d.contorno))
            (x0, y0), (x1, y1) = self.px_to_cm(*box[0]), self.px_to_cm(*box[1])
            angle = (degrees(atan2(y1 - y0, x1 - x0)) + 45) % 90 - 45
            cubes.append(Cube(d.color, x, y, angle, d.area))
        cubes.sort(key=lambda c: -c.area)
        return cubes, self.det.dibujar_detecciones(f, detections)


if __name__ == "__main__":
    # Prueba rápida: py vision.py  -> lista los cubos y guarda la imagen anotada
    import yaml
    cfg = yaml.safe_load((Path(__file__).parent / "config" / "arm.yaml").read_text(encoding="utf-8"))
    with TopCamera(cfg) as cam:
        cubes, img = cam.find_cubes()
    for c in cubes:
        print(f"{c.color:9s} ({c.x:5.1f}, {c.y:5.1f}) cm  girado {c.angle:+.0f}°")
    if not cubes:
        print("No hay cubos en la zona.")
    cv2.imwrite(str(Path(__file__).parent / "vision_test.jpg"), img)
    print("Imagen: vision_test.jpg")
