"""Repetir corridas grabadas con el planificador ACTUAL y guardar escenas como tests.

Cada corrida de sort_cubes.py deja logs/<corrida>/ciclos.jsonl con, por ciclo, los cubos vistos,
la decisión tomada y si el agarre salió. Con eso:

  py replay.py logs/<corrida>                      -> qué decidiría hoy en cada ciclo (vs. lo que hizo)
  py replay.py guardar logs/<corrida> 3 grab       -> el ciclo 3 pasa a tests/scenes/ como test:
                                                      el planificador debe decidir "grab" (o push/none)
  (opcional) --color amarillo  --nota "texto"      -> además exige el color del cubo elegido

Así cada falla vista en la mesa queda como test permanente (py -m pytest tests).
"""
import json
import sys
from pathlib import Path

import yaml

from grasp import Cube

HERE = Path(__file__).parent


def cube_dict(c):
    return {"color": c.color, "x": round(c.x, 3), "y": round(c.y, 3), "angle": round(c.angle, 2)}


def scene_cubes(items):
    return [Cube(d["color"], d["x"], d["y"], d["angle"]) for d in items]


def read_cycles(run_dir):
    """Ciclos de una corrida: une el evento 'decision' con su 'result' (si lo hubo)."""
    cycles = {}
    for line in (Path(run_dir) / "ciclos.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        cycles.setdefault(r["cycle"], {}).update({k: v for k, v in r.items() if k != "event"})
    return [cycles[k] for k in sorted(cycles)]


def replay(run_dir):
    from planner import decide
    cfg = yaml.safe_load((HERE / "config" / "arm.yaml").read_text(encoding="utf-8"))
    for c in read_cycles(run_dir):
        now = decide(cfg, scene_cubes(c["cubes"]), to=c.get("to"))
        res = {True: "salió", False: "FALLÓ"}.get(c.get("ok"), "-")
        same = "igual" if now.kind == c.get("kind") else "DISTINTO"
        print(f"ciclo {c['cycle']:2d}: entonces {c.get('kind', '?'):5s} ({res})  hoy {now.kind:5s} [{same}]  {now.message}")


def save_scene(run_dir, cycle, expect, color=None, note=""):
    c = next(c for c in read_cycles(run_dir) if c["cycle"] == int(cycle))
    name = f"{Path(run_dir).name}_c{cycle}"
    out = HERE / "tests" / "scenes" / f"{name}.json"
    data = {"source": f"{Path(run_dir).name} ciclo {cycle}", "note": note, "expect": expect,
            "expect_color": color, "to": c.get("to"), "cubes": c["cubes"]}
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("escena guardada:", out)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__)
    elif a[0] == "guardar":
        opts = dict(zip(a[4::2], a[5::2]))
        save_scene(a[1], a[2], a[3], opts.get("--color"), opts.get("--nota", ""))
    else:
        replay(a[0])
