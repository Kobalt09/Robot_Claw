"""Mover un servo a mano para calibrar y anotar pulsos.

Uso:  python3 servo_jog.py            (puerto de arm.yaml)
      python3 servo_jog.py COM6       (otro puerto)

Comandos: +  -  (10 us)   ++  --  (50 us)   número = ir a ese pulso
          c = cambiar canal   p = ver todos los canales   q = salir
"""
import os
import sys
from pathlib import Path

import yaml
from maestro import Maestro

cfg = yaml.safe_load((Path(__file__).parent / "config" / "arm.yaml").read_text(encoding="utf-8"))
port = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PERRY_PORT", cfg["port"])
names = {j["channel"]: n for n, j in cfg["joints"].items()}
names[cfg["gripper"]["channel"]] = "pinza"
limits = {j["channel"]: (j["min"], j["max"]) for j in cfg["joints"].values()}
limits[cfg["gripper"]["channel"]] = (cfg["gripper"]["min"], cfg["gripper"]["max"])

with Maestro(port, limits=limits) as m:
    for ch in names:
        m.set_speed(ch, cfg["speed"])
        m.set_acceleration(ch, cfg["acceleration"])
    ch = int(input("Canal: "))
    us = m.get_us(ch) or 1500
    print(__doc__.split("Comandos:")[1])
    while True:
        cmd = input(f"[{ch} {names.get(ch, '?')}] {us:.0f} us > ").strip()
        if cmd == "q":
            break
        if cmd == "c":
            ch = int(input("Canal: "))
            us = m.get_us(ch) or 1500
            continue
        if cmd == "p":
            for c, n in sorted(names.items()):
                print(f"  canal {c:2d} {n:7s} {m.get_us(c):7.0f} us")
            continue
        step = {"+": 10, "-": -10, "++": 50, "--": -50}.get(cmd)
        try:
            us = us + step if step else float(cmd)
        except ValueError:
            print("  comando no válido")
            continue
        m.set_us(ch, us)
