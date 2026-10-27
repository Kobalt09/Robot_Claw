"""Auditar a Perry: ver lo que ve OpenCV y lo que planea hacer la pinza, en vivo.

  py audit.py            -> ventana en vivo (no mueve el brazo: estacionarlo antes con
                            py servo_cmd.py pose vista, si no tapa la zona)
  Teclas: p = pausa, s = guardar captura (en logs/audit/), q = salir

Qué se dibuja (sobre la imagen de la cámara cenital):
  - rectángulo de la zona, círculos de alcance (mínimo y reach.max_r) y el punto bajo la cámara;
  - cada cubo separado: centro, eje y una línea gris desde donde se VEÍA (antes de corregir
    la paralaje) hasta donde se lo ubica;
  - por cada cubo, las huellas de los dedos en sus 2 ejes: verde = libre, rojo = choca;
  - la decisión: cubo elegido con su eje en amarillo grueso, o la flecha del empuje en magenta
    (con la posición esperada de los cubos empujados);
  - panel: lista de cubos, holgura de cada eje, decisión y pulsos que se mandarían.
El mismo dibujo se guarda en cada ciclo de sort_cubes.py (logs/.../plan*.jpg).
"""
import time
from math import hypot, cos, sin, radians, degrees, atan2
from pathlib import Path

import cv2
import numpy as np
import yaml

from grasp import GraspCfg, axis_clearance, closing_dirs, finger_boxes, relative_giro
from planner import decide, reachable
from reach import pulses_at, OutOfTable

HERE = Path(__file__).parent
COLORS = {"azul": (255, 120, 0), "amarillo": (0, 220, 255)}
GREEN, RED, YELLOW, MAGENTA, GRAY, WHITE = (60, 200, 60), (40, 40, 230), (0, 230, 255), (230, 0, 230), (150, 150, 150), (255, 255, 255)


class Drawer:
    def __init__(self, cam, cfg, scale=1.6):
        self.Hinv, self.cfg, self.s = np.linalg.inv(cam.H), cfg, scale
        self.nadir = cam.nadir

    def px(self, x, y):
        p = cv2.perspectiveTransform(np.float32([[[x, y]]]), self.Hinv)[0, 0]
        return int(p[0] * self.s), int(p[1] * self.s)

    def poly(self, img, pts_cm, color, th=1):
        cv2.polylines(img, [np.int32([self.px(x, y) for x, y in pts_cm])], True, color, th, cv2.LINE_AA)


def draw_plan(img, cam, cfg, cubes, decision=None):
    """Imagen anotada con todo lo que el planificador considera. Devuelve imagen + panel."""
    d = Drawer(cam, cfg)
    g = GraspCfg(**cfg["grasp"])
    out = cv2.resize(img, None, fx=d.s, fy=d.s)
    decision = decision or decide(cfg, cubes)

    # zona, alcance y punto bajo la cámara
    d.poly(out, cfg["camera"]["corners_cm"], WHITE, 1)
    rows = cfg["reach"]["rows"]
    for r, col in ((min(row["r"] for row in rows), GRAY), (cfg["reach"]["max_r"], RED)):
        pts = [(r * cos(radians(a)), r * sin(radians(a))) for a in range(-60, 61, 3)]
        cv2.polylines(out, [np.int32([d.px(*p) for p in pts])], False, col, 1, cv2.LINE_AA)
    cv2.drawMarker(out, d.px(*d.nadir), GRAY, cv2.MARKER_STAR, 14, 1)
    cv2.drawMarker(out, d.px(0, 0), WHITE, cv2.MARKER_CROSS, 18, 2)

    # cubos: paralaje, huellas de los dedos en ambos ejes, centro y eje
    for c in cubes:
        if getattr(c, "raw_x", 0):
            cv2.line(out, d.px(c.raw_x, c.raw_y), d.px(c.x, c.y), GRAY, 1, cv2.LINE_AA)
        if reachable(cfg, c):
            for direc in closing_dirs(c):
                free = axis_clearance(c, cubes, direc, g) >= 0
                for box in finger_boxes(c, direc, g):
                    d.poly(out, box, GREEN if free else RED, 1)
        col = COLORS.get(c.color, WHITE)
        cv2.drawMarker(out, d.px(c.x, c.y), col, cv2.MARKER_TILTED_CROSS, 12, 2)
        a = radians(c.angle)
        cv2.line(out, d.px(c.x, c.y), d.px(c.x + cos(a) * g.cube / 2, c.y + sin(a) * g.cube / 2), col, 2)

    # decisión
    if decision.kind == "grab":
        c = decision.cube
        cv2.circle(out, d.px(c.x, c.y), int(18 * d.s), YELLOW, 2, cv2.LINE_AA)
        for box in finger_boxes(c, decision.grasp_dir, g):
            d.poly(out, box, YELLOW, 3)
    elif decision.kind == "push":
        p = decision.plan
        cv2.arrowedLine(out, d.px(*p.start), d.px(*p.end), MAGENTA, 3, cv2.LINE_AA, tipLength=0.25)
        for old, new in zip(cubes, p.predicted):
            if (old.x, old.y) != (new.x, new.y):
                pts = [(new.x + u * g.cube / 2 * cos(radians(new.angle)) - v * g.cube / 2 * sin(radians(new.angle)),
                        new.y + u * g.cube / 2 * sin(radians(new.angle)) + v * g.cube / 2 * cos(radians(new.angle)))
                       for u, v in ((1, 1), (1, -1), (-1, -1), (-1, 1))]
                d.poly(out, pts, MAGENTA, 1)

    # panel de texto
    lines = [f"DECISION: {decision.kind.upper()}", decision.message, ""]
    if decision.kind == "grab":
        c = decision.cube
        try:
            lo = pulses_at(cfg, c.x, c.y, level="grip", grasp_dir=decision.grasp_dir)
            lines += ["pulsos al agarrar (us):", "  " + "  ".join(f"{k[:3]} {v:.0f}" for k, v in lo.items()),
                      f"giro relativo: {relative_giro(c, decision.grasp_dir):+.0f} grados", ""]
        except OutOfTable as e:
            lines += [f"fuera de tabla: {e}", ""]
    lines.append(" color      x     y     r   ang   ejeA   ejeB")
    for c in cubes:
        cl = [axis_clearance(c, cubes, direc, g) for direc in closing_dirs(c)]
        txt = "  ".join("choca" if v < 0 else f"{v:4.1f}" for v in cl)
        flag = "" if reachable(cfg, c) else "  FUERA"
        lines.append(f" {c.color[:8]:8s} {c.x:5.1f} {c.y:5.1f} {hypot(c.x, c.y):5.1f} {c.angle:+4.0f}  {txt}{flag}")
    lines += ["", "verde = eje libre   rojo = choca", "amarillo = agarre elegido", "magenta = empuje",
              "gris = corrimiento por paralaje", f"{time.strftime('%H:%M:%S')}"]
    panel = np.full((out.shape[0], 470, 3), 30, np.uint8)
    for i, t in enumerate(lines):
        cv2.putText(panel, t, (8, 22 + i * 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    YELLOW if i == 0 else WHITE, 1, cv2.LINE_AA)
    return np.hstack([out, panel])


def main():
    from vision import TopCamera, save_image
    cfg = yaml.safe_load((HERE / "config" / "arm.yaml").read_text(encoding="utf-8"))
    out_dir = HERE / cfg["sort"]["log_dir"] / "audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    paused, view = False, None
    with TopCamera(cfg) as cam:
        while True:
            if not paused or view is None:
                cubes, img = cam.find_cubes()
                view = draw_plan(img, cam, cfg, cubes)
            cv2.imshow("Perry - auditoria (q salir, p pausa, s guardar)", view)
            k = cv2.waitKey(150) & 0xFF
            if k == ord("q"):
                break
            if k == ord("p"):
                paused = not paused
            if k == ord("s"):
                f = out_dir / f"{time.strftime('%Y-%m-%d_%H-%M-%S')}.jpg"
                save_image(f, view); print("guardado", f)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
