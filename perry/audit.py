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
import unicodedata
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
ORANGE = (0, 140, 255)
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


def _ascii(t):
    """OpenCV no dibuja tildes ni '°': se pasan a ASCII."""
    return unicodedata.normalize("NFKD", t.replace("°", " grados")).encode("ascii", "ignore").decode()


def _square_pts(c, side):
    a = radians(c.angle)
    return [(c.x + u * side / 2 * cos(a) - v * side / 2 * sin(a), c.y + u * side / 2 * sin(a) + v * side / 2 * cos(a))
            for u, v in ((1, 1), (1, -1), (-1, -1), (-1, 1))]


def _tag(img, pt, text, color):
    (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
    x, y = pt[0] + 8, pt[1] + 18
    cv2.rectangle(img, (x - 2, y - h - 3), (x + w + 2, y + 3), (20, 20, 20), -1)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1, cv2.LINE_AA)


def draw_plan(img, cam, cfg, cubes, decision=None):
    """Imagen anotada con todo lo que el planificador considera. Devuelve imagen + panel."""
    d = Drawer(cam, cfg)
    g = GraspCfg(**cfg["grasp"])
    clean = getattr(cam, "last_frame", None)
    out = cv2.resize(clean if clean is not None else img, None, fx=d.s, fy=d.s)
    decision = decision or decide(cfg, cubes)

    # zona, alcance y punto bajo la cámara
    d.poly(out, cfg["camera"]["corners_cm"], WHITE, 1)
    rows = cfg["reach"]["rows"]
    for r, col in ((min(row["r"] for row in rows), GRAY), (cfg["reach"]["max_r"], RED)):
        pts = [(r * cos(radians(a)), r * sin(radians(a))) for a in range(-60, 61, 3)]
        cv2.polylines(out, [np.int32([d.px(*p) for p in pts])], False, col, 1, cv2.LINE_AA)
    cv2.drawMarker(out, d.px(*d.nadir), GRAY, cv2.MARKER_STAR, 14, 1)
    cv2.drawMarker(out, d.px(0, 0), WHITE, cv2.MARKER_CROSS, 18, 2)

    # cubos: paralaje, huellas de los dedos (finas y tenues), centro y eje
    target = decision.cube if decision.kind in ("grab", "push") else None
    layer = out.copy()
    for c in cubes:
        if getattr(c, "raw_x", 0):
            cv2.line(out, d.px(c.raw_x, c.raw_y), d.px(c.x, c.y), GRAY, 1, cv2.LINE_AA)
        if reachable(cfg, c) and c is not target:
            for direc in closing_dirs(c):
                free = axis_clearance(c, cubes, direc, g) >= 0
                for box in finger_boxes(c, direc, g):
                    d.poly(layer, box, GREEN if free else RED, 1)
    out = cv2.addWeighted(layer, 0.45, out, 0.55, 0)          # huellas atenuadas: no tapan la decisión
    for c in cubes:
        col = COLORS.get(c.color, WHITE)
        cv2.polylines(out, [np.int32([d.px(*q) for q in _square_pts(c, g.cube)])], True, col, 2, cv2.LINE_AA)

    # decisión, bien visible
    if decision.kind == "grab":
        c = decision.cube
        cv2.polylines(out, [np.int32([d.px(*q) for q in _square_pts(c, g.cube)])], True, ORANGE, 4, cv2.LINE_AA)
        for box in finger_boxes(c, decision.grasp_dir, g):
            d.poly(out, box, ORANGE, 3)
        _tag(out, d.px(c.x, c.y), "AGARRAR", ORANGE)
    elif decision.kind == "push":
        p = decision.plan
        ghost = out.copy()
        for old, new in zip(cubes, p.predicted):
            if (old.x, old.y) != (new.x, new.y):
                cv2.fillPoly(ghost, [np.int32([d.px(*q) for q in _square_pts(new, g.cube)])], MAGENTA)
                cv2.line(out, d.px(old.x, old.y), d.px(new.x, new.y), MAGENTA, 1, cv2.LINE_AA)
        out = cv2.addWeighted(ghost, 0.35, out, 0.65, 0)       # dónde quedarían los cubos (fantasma)
        a = degrees(atan2(*p.direction[::-1]))
        pusher = [(p.start[0] + u * 0.5 * cos(radians(a)) - v * 0.95 * sin(radians(a)),
                   p.start[1] + u * 0.5 * sin(radians(a)) + v * 0.95 * cos(radians(a)))
                  for u, v in ((1, 1), (1, -1), (-1, -1), (-1, 1))]
        cv2.fillPoly(out, [np.int32([d.px(*q) for q in pusher])], MAGENTA)
        cv2.arrowedLine(out, d.px(*p.start), d.px(*p.end), MAGENTA, 6, cv2.LINE_AA, tipLength=0.45)
        cv2.polylines(out, [np.int32([d.px(*q) for q in _square_pts(p.cube, g.cube)])], True, ORANGE, 4, cv2.LINE_AA)
        _tag(out, d.px(*p.start), "1", MAGENTA)
        _tag(out, d.px(*p.end), "2", MAGENTA)

    # cartel con la decisión en palabras (2 líneas)
    words = ({"grab": "PROXIMO: ", "push": "PROXIMO: ", "none": "NADA QUE HACER: "}[decision.kind]
             + _ascii(decision.message)).split()
    l1, l2 = "", ""
    for wd in words:
        if not l2 and cv2.getTextSize(l1 + " " + wd, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0][0] < out.shape[1] - 20:
            l1 = (l1 + " " + wd).strip()
        else:
            l2 = (l2 + " " + wd).strip()
    col = MAGENTA if decision.kind == "push" else ORANGE if decision.kind == "grab" else WHITE
    cv2.rectangle(out, (0, 0), (out.shape[1], 70), (20, 20, 20), -1)
    cv2.putText(out, l1, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2, cv2.LINE_AA)
    cv2.putText(out, l2, (10, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2, cv2.LINE_AA)

    # zoom de la zona (para ver el racimo y la flecha en grande)
    zx = [d.px(x, y) for x, y in cfg["camera"]["corners_cm"]]
    x0, x1 = max(0, min(q[0] for q in zx) - 40), min(out.shape[1], max(q[0] for q in zx) + 40)
    y0, y1 = max(70, min(q[1] for q in zx) - 40), min(out.shape[0], max(q[1] for q in zx) + 40)
    zoom = out[y0:y1, x0:x1]
    zoom = cv2.resize(zoom, (560, int(560 * zoom.shape[0] / max(1, zoom.shape[1]))))

    # panel de texto
    lines = [f"DECISION: {decision.kind.upper()}", _ascii(decision.message)[:62], ""]
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
    lines += ["", "NARANJA = cubo elegido y donde bajan los dedos", "MAGENTA: 1 = baja la pinza cerrada, flecha = empuje,",
              "  2 = hasta donde llega, relleno = donde quedan cubos", "tenue: verde = eje libre, rojo = choca",
              "gris = corrimiento por paralaje", f"{time.strftime('%H:%M:%S')}"]
    panel = np.full((out.shape[0], 560, 3), 30, np.uint8)
    zh = min(zoom.shape[0], out.shape[0] // 2)
    panel[:zh] = zoom[:zh]
    cv2.putText(panel, "ZOOM DE LA ZONA", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, WHITE, 1, cv2.LINE_AA)
    for i, t in enumerate(lines[2:]):
        cv2.putText(panel, t, (8, zh + 24 + i * 19), cv2.FONT_HERSHEY_SIMPLEX, 0.45, WHITE, 1, cv2.LINE_AA)
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
