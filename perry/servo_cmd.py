"""Comandos sueltos para la Maestro: cada llamada hace una cosa y termina.

Pensado para usarlo desde Claude Code o desde scripts.

  py servo_cmd.py status                 pulso actual de todos los canales
  py servo_cmd.py set 2 1450             canal 2 a 1450 us (respeta min/max de arm.yaml)
  py servo_cmd.py nudge 2 -20            mueve el canal 2 veinte us
  py servo_cmd.py pose inicio            va a una posición grabada en arm.yaml

Puerto: variable PERRY_PORT (en Windows, por ejemplo COM6) o el de arm.yaml.
"""
import os
import sys
from pathlib import Path

import yaml
from maestro import Maestro

cfg = yaml.safe_load((Path(__file__).parent / "config" / "arm.yaml").read_text(encoding="utf-8"))
port = os.environ.get("PERRY_PORT", cfg["port"])
names = {j["channel"]: n for n, j in cfg["joints"].items()}
names[cfg["gripper"]["channel"]] = "pinza"
limits = {j["channel"]: (j["min"], j["max"]) for j in cfg["joints"].values()}
limits[cfg["gripper"]["channel"]] = (cfg["gripper"]["min"], cfg["gripper"]["max"])


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd = argv[0]
    with Maestro(port, limits=limits) as m:
        for ch in names:
            m.set_speed(ch, cfg["speed"])
            m.set_acceleration(ch, cfg["acceleration"])
        if cmd == "status":
            for c, n in sorted(names.items()):
                print(f"canal {c:2d} {n:7s} {m.get_us(c):7.0f} us")
        elif cmd == "set":
            ch, us = int(argv[1]), float(argv[2])
            m.set_us(ch, us); m.wait()
            print(f"canal {ch} ({names.get(ch, '?')}) -> {m.get_us(ch):.0f} us")
        elif cmd == "nudge":
            ch, d = int(argv[1]), float(argv[2])
            m.set_us(ch, m.get_us(ch) + d); m.wait()
            print(f"canal {ch} ({names.get(ch, '?')}) -> {m.get_us(ch):.0f} us")
        elif cmd == "pose":
            pose = cfg["poses"][argv[1]]
            missing = [j for j, v in pose.items() if v is None]
            if missing:
                raise SystemExit(f"La pose '{argv[1]}' no tiene pulso para: {', '.join(missing)}")
            for j, us in pose.items():
                m.set_us(cfg["joints"][j]["channel"], us)
            m.wait()
            print(f"pose {argv[1]} lista")
        else:
            raise SystemExit(f"Comando desconocido: {cmd}\n{__doc__}")


if __name__ == "__main__":
    main(sys.argv[1:])
