"""Prueba de precisión del brazo (al estilo de la tesis de Lugo, pero automática).

Con UN solo cubo en la zona, Perry lo agarra y lo deja en puntos conocidos (arm.yaml: precision.points).
Después de cada uno se estaciona y la cámara mide dónde quedó: la diferencia es el error del brazo
en esa zona. Al final: error por punto, promedio, error cuadrático medio (RMS) y aviso si pasa de
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
        for i, (tx, ty) in enumerate(p["points"], 1):
            check()
            say(f"Precisión {i}/{len(p['points'])}: llevando el cubo a ({tx}, {ty})")
            try:
                pick(cfg, m, cube, cube.angle, check)
            except OutOfTable as e:
                log(f"  El cubo quedó fuera de alcance ({e}): termino la prueba con lo medido.")
                break
            g = cfg["gripper"]
            high = pulses_at(cfg, tx, ty, level="approach", grasp_dir=90.0)
            low = pulses_at(cfg, tx, ty, level="grip", grasp_dir=90.0)
            move_via_top(m, cfg, high)
            lower_shoulder(m, cfg, low["hombro"] + p["place_lift_us"])
            m.set_us(g["channel"], g["open"]); m.wait(); time.sleep(0.3)
            go_up(cfg, m)
            cubes, _ = look(cfg, m, cam, log, f"precision_{i}")
            got = min(cubes, key=lambda c: hypot(c.x - tx, c.y - ty), default=None)
            if got is None or hypot(got.x - tx, got.y - ty) > p["lost_cm"]:
                log(f"  ({tx}, {ty}): no encuentro el cubo cerca del punto. Detengo la prueba.")
                pairs.append(((tx, ty), None))
                break
            pairs.append(((tx, ty), (got.x, got.y)))
            log(f"  ({tx:5.1f}, {ty:5.1f}) -> quedó en ({got.x:5.2f}, {got.y:5.2f}): "
                f"error {hypot(got.x - tx, got.y - ty) * 10:.1f} mm")
            cube = got
    except Cancelled:
        log("Prueba de precisión CANCELADA."); go_up(cfg, m)
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
