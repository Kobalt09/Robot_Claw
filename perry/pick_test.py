"""Primer agarre automático, sin cámara.

Pon un cubo a mano en (x, y) y Perry lo lleva al contenedor de su color.

  python3 pick_test.py 16 0 azul              -> solo muestra ángulos y pulsos (no mueve nada)
  python3 pick_test.py 16 0 azul --run        -> ejecuta el movimiento
  python3 pick_test.py 16 0 azul --run --angle 30   (cubo girado 30°)
"""
import argparse
import os
from pathlib import Path

import yaml
from kinematics import inverse_kinematics, angle_to_us, OutOfReach
from maestro import Maestro

ORDER = ["base", "hombro", "codo", "muneca", "giro"]


def load_cfg():
    return yaml.safe_load((Path(__file__).parent / "config" / "arm.yaml").read_text(encoding="utf-8"))


def pulses_for(cfg, x, y, z, angle):
    deg = inverse_kinematics(x, y, z, cfg["links"], angle)
    return deg, {j: angle_to_us(cfg["joints"][j], deg[j]) for j in ORDER}


def move(m, cfg, pulses, label):
    print(f"-> {label}")
    for j in ORDER:
        if pulses.get(j) is not None:
            m.set_us(cfg["joints"][j]["channel"], pulses[j])
    if not m.wait():
        print("  [aviso] los servos tardaron demasiado; revisar")


def check_ready(cfg, container):
    missing = [f"joints.{j}.cal" for j in ORDER if any(p is None for _, p in cfg["joints"][j]["cal"])]
    missing += [f"gripper.{k}" for k in ("open", "closed") if cfg["gripper"][k] is None]
    missing += [f"poses.{p}.{j}" for p in ("inicio", container) for j in ORDER if cfg["poses"][p][j] is None]
    if missing:
        raise SystemExit("Faltan datos en arm.yaml:\n  " + "\n  ".join(missing))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("x", type=float)
    ap.add_argument("y", type=float)
    ap.add_argument("color", choices=["azul", "amarillo"])
    ap.add_argument("--angle", type=float, default=0.0, help="giro del cubo visto desde arriba (grados)")
    ap.add_argument("--run", action="store_true", help="mover el brazo (sin esto solo muestra el cálculo)")
    a = ap.parse_args()

    cfg = load_cfg()
    z, za = cfg["grip_z"], cfg["grip_z"] + cfg["approach_z"]
    container = cfg["containers"][a.color]
    try:
        deg, low = pulses_for(cfg, a.x, a.y, z, a.angle)
        _, high = pulses_for(cfg, a.x, a.y, za, a.angle)
    except OutOfReach as e:
        raise SystemExit(f"No se puede: {e}")
    except ValueError as e:
        deg = inverse_kinematics(a.x, a.y, z, cfg["links"], a.angle)
        print("Ángulos:", ", ".join(f"{k} {v:.1f}°" for k, v in deg.items()))
        raise SystemExit(f"No se pueden calcular pulsos: {e}")

    print("Ángulos:", ", ".join(f"{k} {v:.1f}°" for k, v in deg.items()))
    print("Pulsos al agarrar:", ", ".join(f"{k} {v:.0f}" for k, v in low.items()))
    if not a.run:
        print("Modo prueba: no se movió nada. Agrega --run para ejecutar.")
        return

    check_ready(cfg, container)
    limits = {j["channel"]: (j["min"], j["max"]) for j in cfg["joints"].values()}
    g = cfg["gripper"]
    limits[g["channel"]] = (g["min"], g["max"])
    with Maestro(os.environ.get("PERRY_PORT", cfg["port"]), limits=limits) as m:
        for ch in limits:
            m.set_speed(ch, cfg["speed"])
            m.set_acceleration(ch, cfg["acceleration"])
        move(m, cfg, cfg["poses"]["inicio"], "inicio")
        m.set_us(g["channel"], g["open"]); m.wait()
        move(m, cfg, high, f"sobre el cubo ({a.x}, {a.y})")
        move(m, cfg, low, "bajar")
        print("-> cerrar pinza"); m.set_us(g["channel"], g["closed"]); m.wait()
        move(m, cfg, high, "subir")
        move(m, cfg, cfg["poses"][container], f"contenedor {container}")
        print("-> soltar"); m.set_us(g["channel"], g["open"]); m.wait()
        move(m, cfg, cfg["poses"]["inicio"], "inicio")
    print("Listo.")


if __name__ == "__main__":
    main()
