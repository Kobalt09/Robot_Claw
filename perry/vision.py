"""Visión de Perry: encontrar cubos en la zona con la cámara cenital.

Usa el detector de colores del equipo (codigo_python/detector_colores.py) y le agrega:
- homografía píxel -> cm con las 4 esquinas del rectángulo de la zona (arm.yaml: camera);
- filtro de zona: solo cuentan los cubos dentro del rectángulo (descarta cinta, contenedores);
- ángulo del cubo visto desde arriba, para girar la pinza.

Todo número vive en arm.yaml. Si mueven la cámara: py calibrate_camera.py
"""
import os
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


def wait_still(grab, pause=0.3, tol=4.0, timeout=4.0):
    """Espera a que la escena esté quieta: dos cuadros seguidos (separados `pause` s) casi iguales.

    La webcam entrega los cuadros con retraso: justo después de estacionar, el último cuadro puede
    mostrar todavía el brazo cruzando la zona. Devuelve (cuadro, quieto?)."""
    t0 = time.time()
    prev = grab()
    while True:
        time.sleep(pause)
        cur = grab()
        if float(np.mean(cv2.absdiff(prev, cur))) <= tol:
            return cur, True
        if time.time() - t0 > timeout:
            return cur, False
        prev = cur


def zone_blobs_cm2(frame, cfg):
    """Áreas (cm², de mayor a menor) de lo que hay dentro del azul de la zona y no es fondo azul.

    Cubos, la pala de un carro o el brazo: todo lo que tapa el azul. El azul se toma de las esquinas de la
    homografía (camera.corners_px), sin un borde de settle.edge_px donde la cinta lo ensucia.
    """
    c, st = cfg["camera"], cfg["settle"]
    zone = np.zeros(frame.shape[:2], np.uint8)
    cv2.fillPoly(zone, [np.int32(c["corners_px"])], 255)
    k = 2 * st["edge_px"] + 1
    zone = cv2.erode(zone, np.ones((k, k), np.uint8))
    hsv = cv2.cvtColor(cv2.GaussianBlur(frame, (5, 5), 0), cv2.COLOR_BGR2HSV)
    lo, hi = c["zone_bg_hsv"]
    bg = cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
    fg = cv2.morphologyEx(cv2.bitwise_and(zone, cv2.bitwise_not(bg)), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    H = cv2.getPerspectiveTransform(np.float32(c["corners_px"]), np.float32(c["corners_cm"]))
    areas = []
    for cnt in cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
        areas.append(float(cv2.contourArea(cv2.perspectiveTransform(np.float32(cnt), H))))
    return sorted(areas, reverse=True)


def zone_is_clear(frame, cfg):
    """True si dentro de la zona no hay ningún objeto más grande que settle.big_object_cm2 (carro o brazo)."""
    blobs = zone_blobs_cm2(frame, cfg)
    return not blobs or blobs[0] < cfg["settle"]["big_object_cm2"]


def parallax_correct(x, y, nadir, cam_height, obj_height):
    """Corrige la paralaje de un objeto de altura obj_height visto desde arriba.

    La homografía es para el plano de la mesa, pero la cámara ve la cara de arriba del cubo:
    por perspectiva, aparece corrido hacia afuera del punto de la mesa que está justo debajo
    de la cámara (nadir), en la proporción obj_height / cam_height. Se lo trae de vuelta.
    """
    k = 1.0 - obj_height / cam_height
    return nadir[0] + (x - nadir[0]) * k, nadir[1] + (y - nadir[1]) * k


def _square_angle(pts):
    """Ángulo (en [-45, 45)) de un cubo a partir de sus puntos, con el rectángulo mínimo."""
    box = cv2.boxPoints(cv2.minAreaRect(np.float32(pts)))
    e = box[1] - box[0]
    return (degrees(atan2(float(e[1]), float(e[0]))) + 45) % 90 - 45


def split_region(points_cm, area_cm2, cube):
    """Separa una mancha de cubos del mismo color pegados en cubos individuales.

    points_cm: puntos del INTERIOR de la mancha, ya en cm (N x 2); area_cm2: su área.
    Cuántos cubos hay sale del área (no de la forma), así funciona con filas prolijas, pares
    escalonados, formas de L o cubos girados distinto. Los puntos se reparten con k-means y
    cada grupo da el centro y el ángulo de un cubo. Devuelve [(x, y, ángulo en [-45, 45))].
    """
    pts = np.float32(points_cm)
    n = max(1, int(area_cm2 / (cube * cube) + 0.45))   # tolera que la segmentación coma borde
    if n == 1 or len(pts) < n:
        c = pts.mean(axis=0)
        return [(float(c[0]), float(c[1]), _square_angle(pts))]
    cv2.setRNGSeed(0)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 1e-3)
    _, labels, centers = cv2.kmeans(pts, n, None, crit, 10, cv2.KMEANS_PP_CENTERS)
    labels = labels.ravel()
    return [(float(c[0]), float(c[1]), _square_angle(pts[labels == k])) for k, c in enumerate(centers)]


@dataclass
class Cube:
    color: str
    x: float          # cm, hacia la zona
    y: float          # cm, a la izquierda
    angle: float      # grados en [-45, 45): giro del cubo visto desde arriba
    area: float       # píxeles
    raw_x: float = 0.0  # posición antes de corregir la paralaje (para auditar)
    raw_y: float = 0.0


CAMERA_ENV = "PERRY_CAMERA"


def camera_candidates(c, env=os.environ):
    """Índices de cámara a probar, en orden.

    Con PERRY_CAMERA (como PERRY_PORT) cada PC fija su cámara sin tocar arm.yaml: solo ese índice,
    sin caer a otra en silencio (una cámara integrada abre sin error y el panel usaría la equivocada).
    Sin la variable: camera.index primero y después los demás hasta camera.max_index.
    """
    fixed = env.get(CAMERA_ENV, "").strip()
    if fixed:
        try:
            return [int(fixed)]
        except ValueError:
            raise ValueError(f"{CAMERA_ENV}={fixed!r}: debe ser un número de cámara (0, 1, 2...)") from None
    first = c["index"]
    return [first] + [i for i in range(c["max_index"]) if i != first]


class TopCamera:
    """Cámara cenital con la homografía de arm.yaml. Úsala con `with`."""

    def __init__(self, cfg):
        self._setup_detection(cfg)
        c = self.cfg
        tried = camera_candidates(c)
        for idx in tried:
            try:
                self.cam = CapturaCamara(indice_camara=idx)
                break
            except RuntimeError:
                continue
        else:
            hint = f" (la fijó {CAMERA_ENV})" if os.environ.get(CAMERA_ENV, "").strip() else ""
            raise RuntimeError(f"No se pudo abrir la cámara en {tried}{hint}. "
                               f"Ver cuál es la cenital: py list_cameras.py")
        c["index"] = idx
        print(f"[cámara] usando el índice {idx} ({CAMERA_ENV} o camera.index para cambiarlo)")
        time.sleep(c["warmup_s"])
        # punto de la mesa justo debajo de la cámara: el de arm.yaml, o el centro de la imagen
        if self.nadir is None:
            h, w = self.frame().shape[:2]
            self.nadir = self.px_to_cm(w / 2, h / 2)

    def _setup_detection(self, cfg):
        """Homografía y colores, sin abrir la cámara (así se prueba con fotos guardadas)."""
        c = cfg["camera"]
        self.cfg = c
        self.cube_cm = cfg["grasp"]["cube"]
        self.H = cv2.getPerspectiveTransform(np.float32(c["corners_px"]), np.float32(c["corners_cm"]))
        self.det = DetectorColores(area_minima=c["min_area_px"])
        self.det.rangos_colores.clear()
        for name, ranges in c["colors"].items():
            self.det.configurar_color(name, [(np.array(lo, np.uint8), np.array(hi, np.uint8)) for lo, hi in ranges])
        self.nadir = tuple(c["nadir_cm"]) if c.get("nadir_cm") else None   # None: el centro de la imagen

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

    def still_frame(self):
        f, ok = wait_still(self.frame, self.cfg.get("still_pause_s", 0.3), self.cfg.get("still_tol", 4.0),
                           self.cfg.get("still_timeout_s", 4.0))
        self.last_still = ok
        return f

    def find_cubes(self, frame=None):
        """Cubos dentro de la zona, el más grande primero. Devuelve (cubos, imagen anotada)."""
        f = self.frame() if frame is None else frame
        self.last_frame = f   # imagen limpia, para la interfaz de auditoría
        if self.nadir is None:          # sin cámara abierta (pruebas con fotos): el centro de la imagen
            self.nadir = self.px_to_cm(f.shape[1] / 2, f.shape[0] / 2)
        z = self.cfg["zone"]
        cubes = []
        detections = self.det.procesar_frame(f)
        for d in detections:
            x, y = self.px_to_cm(*d.centroide)
            if not (z["x_min"] <= x <= z["x_max"] and abs(y) <= z["y_abs"]):
                continue
            # interior de la mancha a cm (sin perspectiva) y separar cubos pegados del mismo color
            mask = np.zeros(f.shape[:2], np.uint8)
            cv2.drawContours(mask, [d.contorno], -1, 255, -1)
            vs, us = np.nonzero(mask)
            pix = np.float32(np.column_stack([us, vs])).reshape(-1, 1, 2)
            pts = cv2.perspectiveTransform(pix, self.H).reshape(-1, 2)
            border = cv2.perspectiveTransform(np.float32(d.contorno).reshape(-1, 1, 2), self.H)
            parts = split_region(pts, cv2.contourArea(border), self.cube_cm)
            for rx, ry, angle in parts:
                px, py = parallax_correct(rx, ry, self.nadir, self.cfg["height_cm"], self.cube_cm)
                cubes.append(Cube(d.color, px, py, angle, d.area / len(parts), rx, ry))
        cubes.sort(key=lambda c: -c.area)
        img = self.det.dibujar_detecciones(f, detections)
        Hinv = np.linalg.inv(self.H)
        for c in cubes:   # centro y una arista de cada cubo separado, para revisar a ojo
            a = np.radians(c.angle)
            ends = np.float32([[c.x, c.y], [c.x + np.cos(a) * self.cube_cm / 2, c.y + np.sin(a) * self.cube_cm / 2]])
            (p0, p1) = cv2.perspectiveTransform(ends.reshape(-1, 1, 2), Hinv).reshape(-1, 2)
            cv2.drawMarker(img, (int(p0[0]), int(p0[1])), (0, 255, 0), cv2.MARKER_TILTED_CROSS, 8, 2)
            cv2.line(img, (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])), (0, 255, 0), 1)
        return cubes, img


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
