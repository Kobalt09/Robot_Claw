"""¿Cuál es la cámara cenital? Prueba los índices 0..camera.max_index-1 y guarda una foto de cada uno.

    py list_cameras.py

Cerrar antes el panel (audit_web.py) y cualquier programa que use la cámara (Teams, Zoom, la app Cámara).
Las fotos quedan en logs/camaras/camara_<N>.jpg: la que muestra la zona azul desde arriba es la cenital.
Después, en PowerShell, antes de arrancar el panel:

    $env:PERRY_CAMERA = "<N>"
"""
import sys
from pathlib import Path

import cv2
import yaml

from vision import CAMERA_ENV, save_image

HERE = Path(__file__).resolve().parent
cfg = yaml.safe_load((HERE / "config" / "arm.yaml").read_text(encoding="utf-8"))
cam_cfg = cfg["camera"]
backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
out = HERE / cfg["sort"]["log_dir"] / "camaras"
out.mkdir(parents=True, exist_ok=True)

found = []
for i in range(cam_cfg["max_index"]):
    cap = cv2.VideoCapture(i, backend)
    ok, frame = cap.read() if cap.isOpened() else (False, None)
    cap.release()
    if not ok or frame is None:
        print(f"  {i}: sin imagen")
        continue
    path = out / f"camara_{i}.jpg"
    save_image(path, frame)
    found.append(i)
    print(f"  {i}: entrega imagen {frame.shape[1]}x{frame.shape[0]} -> {path}")

if not found:
    print("Ninguna cámara entrega imagen: ¿está conectada?, ¿la usa otro programa?, "
          "¿Windows permite la cámara a las aplicaciones de escritorio?")
else:
    print(f"\nMirá las fotos en {out}. Si la cenital es la N, antes del panel: $env:{CAMERA_ENV} = \"N\"")
