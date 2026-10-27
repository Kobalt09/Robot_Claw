"""Enseñar una fila de la tabla `reach.rows` con un cubo real.

  py teach_row.py                                   -> lista los cubos con su r (no mueve)
  py teach_row.py X Y ANGULO HOMBRO CODO MUNECA     -> deja la pinza abierta, abajo, sobre (X, Y)
  py teach_row.py X Y ANGULO HOMBRO CODO MUNECA --grab   -> además cierra, sube y verifica

Se prueban pulsos hasta que el cubo queda entre los dedos (mirar de costado y de frente) y
--grab lo levanta. Entonces imprime la fila para pegar en arm.yaml (reach.rows), ya sin el
ajuste del resorte (grip_shoulder_offset_us), que la tabla aplica sola.
Pista para empezar: tomar la fila más cercana de arm.yaml. Más cerca de la base = hombro
más alto (hacia atrás) y codo más alto (más cerrado).
"""
import os
import sys
import time
from math import atan2, degrees, hypot
from pathlib import Path

import yaml

from kinematics import angle_to_us
from maestro import Maestro
from reach import move_via_top, lower_shoulder
from vision import TopCamera

HERE = Path(__file__).parent


def main(argv):
    cfg = yaml.safe_load((HERE / "config" / "arm.yaml").read_text(encoding="utf-8"))
    limits = {j["channel"]: (j["min"], j["max"]) for j in cfg["joints"].values()}
    g = cfg["gripper"]
    limits[g["channel"]] = (g["min"], g["max"])
    with Maestro(os.environ.get("PERRY_PORT", cfg["port"]), limits=limits) as m:
        for ch in limits:
            m.set_speed(ch, cfg["speed"]); m.set_acceleration(ch, cfg["acceleration"])
        if len(argv) < 6:
            move_via_top(m, cfg, cfg["poses"]["vista"], precise_base=False)
            with TopCamera(cfg) as cam:
                cubes, _ = cam.find_cubes()
            for c in cubes:
                print(f"{c.color:9s} X {c.x:5.1f}  Y {c.y:5.1f}  ángulo {c.angle:+4.0f}  r = {hypot(c.x, c.y):.2f}")
            return
        x, y, ang, sh, el, wr = map(float, argv[:6])
        if hypot(x, y) > cfg["reach"]["max_r"]:
            raise SystemExit(f"r = {hypot(x, y):.1f} cm supera reach.max_r = {cfg['reach']['max_r']}: el brazo se desploma.")
        base = degrees(atan2(y, x))
        giro = ((ang - base + 45) % 90) - 45
        target = {"base": angle_to_us(cfg["joints"]["base"], base), "giro": angle_to_us(cfg["joints"]["giro"], giro),
                  "codo": el, "muneca": wr, "hombro": sh + cfg["reach"]["approach_shoulder_us"]}
        m.set_us(g["channel"], g["open"]); m.wait()
        move_via_top(m, cfg, target)
        lower_shoulder(m, cfg, sh)
        print(f"Pinza abierta sobre ({x}, {y}), r = {hypot(x, y):.2f}: hombro {sh:.0f}, codo {el:.0f}, muñeca {wr:.0f}")
        if "--grab" not in argv:
            print("Mirar si el cubo queda entre los dedos. Para probar el agarre, repetir con --grab.")
            return
        m.set_us(g["channel"], g["closed"]); m.wait(); time.sleep(0.3)
        for j, us in cfg["travel"].items():
            m.set_us(cfg["joints"][j]["channel"], us); m.wait()
        move_via_top(m, cfg, cfg["poses"]["vista"], precise_base=False)
        with TopCamera(cfg) as cam:
            cubes, _ = cam.find_cubes()
        still = [c for c in cubes if hypot(c.x - x, c.y - y) < cfg["sort"]["same_cube_cm"]]
        if still:
            print(f"FALLÓ: el cubo sigue en ({still[0].x:.1f}, {still[0].y:.1f}). Ajustar y repetir.")
            m.set_us(g["channel"], g["open"]); m.wait()
        else:
            row_sh = sh - cfg["reach"].get("grip_shoulder_offset_us", 0)
            print("AGARRADO (el cubo sigue en la pinza: soltarlo con py servo_cmd.py set 10 750).")
            print(f"Fila para arm.yaml:  - {{r: {hypot(x, y):.2f}, hombro: {row_sh:.0f}, codo: {el:.0f}, muneca: {wr:.0f}}}")


if __name__ == "__main__":
    main(sys.argv[1:])
