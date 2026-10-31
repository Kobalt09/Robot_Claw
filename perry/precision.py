"""Prueba de precisión del brazo (al estilo de la tesis de Lugo, pero automática).

Con UN solo cubo en la zona, Perry lo lleva cerca de cada punto (arm.yaml: precision.points) y ahí
mide el error del brazo con "cerrar y soltar": baja la pinza abierta sobre el cubo, cierra SIN
levantar (los dedos centran el cubo donde la pinza realmente bajó), abre, sube y la cámara mide
cuánto se corrió. Dos veces, con la pinza girada 90°, para tener X e Y. (Agarrar y dejar en el
mismo lugar no sirve: el error se cancela.) Al final: error por punto, promedio, error cuadrático medio (RMS) y aviso si pasa de
precision.threshold_cm (los servos se desajustan con el uso: ver recomendaciones de la tesis).

  py precision.py            -> corre la prueba (también: botón "Prueba de precisión" del panel)
Resultados: logs/precision/<fecha>.json y en el registro de la corrida.
"""
import json
import time
from math import hypot
from pathlib import Path

import yaml

HERE = Path(__file__).parent


def squeeze_error(before_a, after_a, dir_a, before_b, after_b, dir_b):
    """Error del brazo (dx, dy) a partir de dos "cerrar y soltar" en direcciones perpendiculares.

    Al cerrar sin levantar, los dedos centran el cubo entre ellos: el cubo se corre, a lo largo de
    la dirección de cierre, exactamente lo que la pinza bajó corrida. Se proyecta cada corrimiento
    sobre su dirección y se suman (las direcciones son perpendiculares).
    """
    from math import cos, sin, radians
    total = [0.0, 0.0]
    for b, a, d in ((before_a, after_a, dir_a), (before_b, after_b, dir_b)):
        u = (cos(radians(d)), sin(radians(d)))
        k = (a[0] - b[0]) * u[0] + (a[1] - b[1]) * u[1]
        total[0] += k * u[0]; total[1] += k * u[1]
    return total[0], total[1]


def summarize(pairs, threshold):
    """pairs: [((x, y) pedido, (x, y) medido o None)]. Devuelve el resumen de errores."""
    rows, missing = [], 0
    for target, got in pairs:
        if got is None:
            missing += 1
            rows.append({"target": tuple(target), "measured": None, "dx": None, "dy": None, "error": None})
            continue
        dx, dy = got[0] - target[0], got[1] - target[1]
        rows.append({"target": tuple(target), "measured": tuple(got), "dx": dx, "dy": dy, "error": hypot(dx, dy)})
    ok_rows = [r for r in rows if r["error"] is not None]
    n = len(ok_rows) or 1
    rms = (sum(r["error"] ** 2 for r in ok_rows) / n) ** 0.5 if ok_rows else None
    return {
        "rows": rows, "missing": missing, "rms": rms,
        "mean_dx": sum(r["dx"] for r in ok_rows) / n if ok_rows else None,
        "mean_dy": sum(r["dy"] for r in ok_rows) / n if ok_rows else None,
        "worst": max(ok_rows, key=lambda r: r["error"]) if ok_rows else None,
        "ok": missing == 0 and rms is not None and rms <= threshold,
        "threshold": threshold,
    }


def precision_run(cfg, m, cam, log, stop=None, status=None):
    """Corre la prueba con el brazo. Devuelve el resumen (o None si no se pudo empezar)."""
    from reach import pulses_at, move_via_top, lower_shoulder, OutOfTable
    from sort_cubes import look, pick, go_up, Cancelled

    p = cfg["precision"]
    say = status or (lambda t: None)

    def check():
        if stop is not None and stop.is_set():
            raise Cancelled()

    pairs = []
    try:
        cubes, _ = look(cfg, m, cam, log, "precision_inicio")
        if len(cubes) != 1:
            log(f"Prueba de precisión: hace falta exactamente UN cubo en la zona y veo {len(cubes)}.")
            return None
        cube = cubes[0]
        g = cfg["gripper"]

        def nearest(cubes, x, y):
            return min(cubes, key=lambda c: hypot(c.x - x, c.y - y), default=None)

        for i, (tx, ty) in enumerate(p["points"], 1):
            check()
            say(f"Precisión {i}/{len(p['points'])}: llevando el cubo cerca de ({tx}, {ty})")
            try:
                pick(cfg, m, cube, cube.angle, check)
            except OutOfTable as e:
                log(f"  El cubo quedó fuera de alcance ({e}): termino la prueba con lo medido.")
                break
            high = pulses_at(cfg, tx, ty, level="approach", grasp_dir=90.0)
            low = pulses_at(cfg, tx, ty, level="grip", grasp_dir=90.0)
            move_via_top(m, cfg, high)
            lower_shoulder(m, cfg, low["hombro"] + p["place_lift_us"])
            m.set_us(g["channel"], g["open"]); m.wait(); time.sleep(0.3)
            go_up(cfg, m)
            cubes, _ = look(cfg, m, cam, log, f"precision_{i}_dejado")
            c0 = nearest(cubes, tx, ty)
            if c0 is None or hypot(c0.x - tx, c0.y - ty) > p["lost_cm"]:
                log(f"  ({tx}, {ty}): no encuentro el cubo cerca del punto. Detengo la prueba.")
                pairs.append(((tx, ty), None)); break
            # medir el error del brazo AHÍ: cerrar y soltar en dos direcciones perpendiculares
            say(f"Precisión {i}/{len(p['points'])}: midiendo en ({c0.x:.1f}, {c0.y:.1f})")
            seen, prev = [], c0
            for d in (c0.angle, c0.angle + 90.0):
                check()
                hi = pulses_at(cfg, prev.x, prev.y, level="approach", grasp_dir=d)
                lo = pulses_at(cfg, prev.x, prev.y, level="grip", grasp_dir=d)
                m.set_us(g["channel"], g["open"]); m.wait()
                move_via_top(m, cfg, hi)
                lower_shoulder(m, cfg, lo["hombro"])
                m.set_us(g["channel"], g["closed"]); m.wait(); time.sleep(0.3)
                m.set_us(g["channel"], g["open"]); m.wait(); time.sleep(0.2)
                go_up(cfg, m)
                cubes, _ = look(cfg, m, cam, log, f"precision_{i}_cierre{len(seen) + 1}")
                now = nearest(cubes, prev.x, prev.y)
                if now is None:
                    break
                seen.append((prev, now, d)); prev = now
            if len(seen) < 2:
                log(f"  ({c0.x:.1f}, {c0.y:.1f}): perdí el cubo al medir. Detengo la prueba.")
                pairs.append(((c0.x, c0.y), None)); break
            (b1, a1, d1), (b2, a2, d2) = seen
            dx, dy = squeeze_error((b1.x, b1.y), (a1.x, a1.y), d1, (b2.x, b2.y), (a2.x, a2.y), d2)
            pairs.append(((c0.x, c0.y), (c0.x + dx, c0.y + dy)))
            log(f"  en ({c0.x:5.1f}, {c0.y:5.1f}): la pinza baja corrida X {dx * 10:+.1f} mm, Y {dy * 10:+.1f} mm "
                f"({hypot(dx, dy) * 10:.1f} mm)  [dejarlo erró {hypot(c0.x - tx, c0.y - ty) * 10:.0f} mm]")
            cube = prev
    except Cancelled:
        log("Prueba de precisión CANCELADA."); go_up(cfg, m)
    except OutOfTable as e:
        log(f"  Fuera de alcance al medir ({e}): termino la prueba con lo medido."); go_up(cfg, m)
    s = summarize(pairs, p["threshold_cm"])
    if s["rms"] is not None:
        log(f"Precisión: error cuadrático medio {s['rms'] * 10:.1f} mm (umbral {p['threshold_cm'] * 10:.0f} mm), "
            f"sesgo medio X {s['mean_dx'] * 10:+.1f} mm, Y {s['mean_dy'] * 10:+.1f} mm. "
            + ("OK." if s["ok"] else "PASA EL UMBRAL: conviene recalibrar."))
    out = HERE / cfg["sort"]["log_dir"] / "precision"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{time.strftime('%Y-%m-%d_%H-%M-%S')}.json").write_text(json.dumps(s, indent=1), encoding="utf-8")
    move_via_top(m, cfg, cfg["poses"]["vista"], precise_base=False)
    say("Detenido")
    return s


def main():
    from sort_cubes import Log, open_arm
    from vision import TopCamera
    cfg = yaml.safe_load((HERE / "config" / "arm.yaml").read_text(encoding="utf-8"))
    m = open_arm(cfg)
    try:
        with TopCamera(cfg) as cam:
            precision_run(cfg, m, cam, Log(cfg))
    finally:
        m.close()


if __name__ == "__main__":
    main()
