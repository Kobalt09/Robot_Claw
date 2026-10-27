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


def save_image(path, img):
    """Guarda una imagen. cv2.imwrite falla EN SILENCIO en Windows si la ruta tiene tildes
    (p. ej. 'Informática'); codificar en memoria y escribir con Python funciona siempre."""
    ok, buf = cv2.imencode(Path(path).suffix or ".jpg", img)
    if ok:
        Path(path).write_bytes(buf.tobytes())
    return ok


def split_blob(points_cm, cube):
    """Separa una mancha de cubos del mismo color pegados en cubos individuales.

    points_cm: contorno de la mancha ya pasado a cm (N x 2). Los rastrillos dejan los cubos de
    una pasada con la misma orientación, así que la mancha es un rectángulo de n x m cubos:
    se cuenta cuántos caben en cada arista del rectángulo mínimo y se reparte.
    Devuelve [(x, y, ángulo)] con el ángulo en [-45, 45).
    """
    box = cv2.boxPoints(cv2.minAreaRect(np.float32(points_cm)))
    e0, e1 = box[1] - box[0], box[2] - box[1]
    l0, l1 = float(np.hypot(*e0)), float(np.hypot(*e1))
    u0, u1 = e0 / l0, e1 / l1
    n0, n1 = max(1, round(l0 / cube)), max(1, round(l1 / cube))
    c = box.mean(axis=0)
    angle = (degrees(atan2(u0[1], u0[0])) + 45) % 90 - 45
    out = []
    for i in range(n0):
        for j in range(n1):
            p = c + (i - (n0 - 1) / 2) * (l0 / n0) * u0 + (j - (n1 - 1) / 2) * (l1 / n1) * u1
            out.append((float(p[0]), float(p[1]), angle))
    return out


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
        self.cube_cm = cfg["grasp"]["cube"]
        self.H =cv2.getPerspectiveTransform(np.float32(c["corners_px"]), np.float32(c["corners_cm"]))
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
            # contorno a cm (sin perspectiva) y separar cubos pegados del mismo color
            pts = cv2.perspectiveTransform(np.float32(d.contorno).reshape(-1, 1, 2), self.H).reshape(-1, 2)
            parts = split_blob(pts, self.cube_cm)
            for px, py, angle in parts:
                cubes.append(Cube(d.color, px, py, angle, d.area / len(parts)))
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
    save_image(Path(__file__).parent / "vision_test.jpg", img)
    print("Imagen: vision_test.jpg")
