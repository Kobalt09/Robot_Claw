"""Recalibrar la cámara cenital si la movieron (no hace falta tocar código).

  py calibrate_camera.py

Se abre la imagen de la cámara. Haz clic en las 4 esquinas del rectángulo de la hoja
milimetrada, EN ESTE ORDEN (mirando desde el brazo hacia la zona):
  1) lejana izquierda   2) lejana derecha   3) cercana derecha   4) cercana izquierda
Luego pulsa: s = guardar en arm.yaml, r = repetir, q = salir sin guardar.
Antes de empezar, el brazo no debe tapar el rectángulo (py servo_cmd.py pose vista).
"""
import re
import time
from pathlib import Path

import cv2
import numpy as np
import yaml

HERE = Path(__file__).parent
YAML = HERE / "config" / "arm.yaml"
NAMES = ["1 lejana izq.", "2 lejana der.", "3 cercana der.", "4 cercana izq."]


def main():
    cfg = yaml.safe_load(YAML.read_text(encoding="utf-8"))
    c = cfg["camera"]
    cam = cv2.VideoCapture(c["index"], cv2.CAP_DSHOW) if hasattr(cv2, "CAP_DSHOW") else cv2.VideoCapture(c["index"])
    t = time.time()
    while time.time() - t < c["warmup_s"]:
        ok, frame = cam.read()
    cam.release()
    if not ok:
        raise SystemExit(f"No se pudo leer la cámara {c['index']}: revisa camera.index en arm.yaml")

    pts = []

    def click(event, u, v, *_):
        if event == cv2.EVENT_LBUTTONDOWN and len(pts) < 4:
            pts.append((float(u), float(v)))

    cv2.namedWindow("calibrar"); cv2.setMouseCallback("calibrar", click)
    while True:
        img = frame.copy()
        for i, p in enumerate(pts):
            cv2.circle(img, (int(p[0]), int(p[1])), 4, (0, 0, 255), -1)
            cv2.putText(img, NAMES[i][0], (int(p[0]) + 6, int(p[1]) - 6), 0, 0.6, (0, 0, 255), 2)
        msg = f"Clic: {NAMES[len(pts)]}" if len(pts) < 4 else "s = guardar, r = repetir, q = salir"
        cv2.putText(img, msg, (10, 25), 0, 0.7, (0, 0, 255), 2)
        if len(pts) == 4:
            # verificación: el centro del rectángulo debe caer en el centro dibujado
            H = cv2.getPerspectiveTransform(np.float32(c["corners_cm"]), np.float32(pts))
            cm = np.float32(c["corners_cm"])
            ctr = H @ [cm[:, 0].mean(), cm[:, 1].mean(), 1.0]
            cv2.drawMarker(img, (int(ctr[0] / ctr[2]), int(ctr[1] / ctr[2])), (0, 255, 0), cv2.MARKER_CROSS, 20, 2)
        cv2.imshow("calibrar", img)
        k = cv2.waitKey(30) & 0xFF
        if k == ord("r"):
            pts.clear()
        elif k == ord("q"):
            print("Sin cambios."); break
        elif k == ord("s") and len(pts) == 4:
            new = "corners_px: [" + ", ".join(f"[{u:.1f}, {v:.1f}]" for u, v in pts) + "]"
            text = YAML.read_text(encoding="utf-8")
            text = re.sub(r"corners_px: \[\[.*?\]\]", new, text, count=1)
            YAML.write_text(text, encoding="utf-8")
            print(f"Guardado en arm.yaml: {new}")
            break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
