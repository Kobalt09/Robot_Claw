"""Perry clasifica solo: ve los cubos de la zona y los lleva a su contenedor.

  py sort_cubes.py              -> solo mira: lista los cubos y qué haría (no mueve nada)
  py sort_cubes.py --run        -> ciclo completo hasta vaciar la zona
  py sort_cubes.py --run --to amarillo   -> todo al mismo contenedor (pruebas)

Ciclo por cubo: estacionar (para no tapar la cámara) -> detectar -> elegir uno alcanzable ->
abrir -> llegar por arriba con la pinza girada -> bajar lento -> cerrar -> subir -> estacionar
y verificar que ya no está -> contenedor de su color -> soltar.

Reglas para que funcione sin nadie al lado:
- un cubo fuera de la tabla enseñada no se intenta: se avisa y se ignora;
- si tras agarrar el cubo sigue ahí, se reintenta (sort.retries) y luego se ignora ese cubo;
- todo se registra con hora y foto en perry/logs/AAAA-MM-DD_HH-MM-SS/.
Puerto: variable PERRY_PORT (en Windows, por ejemplo COM5) o el de arm.yaml.
"""
import argparse
import os
import time
from math import atan2, degrees, hypot
from pathlib import Path

import cv2
import yaml

from grasp import GraspCfg, choose_grasp, plan_push
from maestro import Maestro
from reach import pulses_at, move_via_top, lower_shoulder, push, OutOfTable
from vision import TopCamera

HERE = Path(__file__).parent


class Log:
    def __init__(self, cfg):
        self.dir = HERE / cfg["sort"]["log_dir"] / time.strftime("%Y-%m-%d_%H-%M-%S")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file = open(self.dir / "registro.txt", "a", encoding="utf-8")

    def __call__(self, msg):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line)
        self.file.write(line + "\n"); self.file.flush()

    def image(self, name, img):
        cv2.imwrite(str(self.dir / f"{time.strftime('%H-%M-%S')}_{name}.jpg"), img)


def reachable(cfg, cube):
    rows = cfg["reach"]["rows"]
    r = hypot(cube.x, cube.y)
    r_max = min(max(row["r"] for row in rows), cfg["reach"].get("max_r", 99))
    return min(row["r"] for row in rows) <= r <= r_max


def look(cfg, m, cam, log, tag):
    """Estaciona el brazo fuera de la vista y devuelve los cubos de la zona."""
    move_via_top(m, cfg, cfg["poses"]["vista"], precise_base=False)
    time.sleep(0.5)  # que se quede quieto antes de la foto
    cubes, img = cam.find_cubes()
    log.image(tag, img)
    return cubes


def pick(cfg, m, cube, grasp_dir):
    """Agarra el cubo cerrando en `grasp_dir` y lo deja arriba, en la pose de traslado."""
    g = cfg["gripper"]
    high = pulses_at(cfg, cube.x, cube.y, level="approach", grasp_dir=grasp_dir)
    low = pulses_at(cfg, cube.x, cube.y, level="grip", grasp_dir=grasp_dir)
    m.set_us(g["channel"], g["open"]); m.wait()
    move_via_top(m, cfg, high)                       # por arriba, base precisa, pinza girada
    lower_shoulder(m, cfg, low["hombro"])            # baja lento
    m.set_us(g["channel"], g["closed"]); m.wait(); time.sleep(0.3)
    for j, us in cfg["travel"].items():              # sube en vertical primero con el hombro
        m.set_us(cfg["joints"][j]["channel"], us); m.wait()


def drop(cfg, m, container):
    g = cfg["gripper"]
    move_via_top(m, cfg, cfg["poses"][container], precise_base=False)
    m.set_us(g["channel"], g["open"]); m.wait(); time.sleep(0.3)
    for j, us in cfg["travel"].items():
        m.set_us(cfg["joints"][j]["channel"], us); m.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="mover el brazo (sin esto solo mira)")
    ap.add_argument("--to", help="mandar todos los cubos a este contenedor (pruebas)")
    a = ap.parse_args()

    cfg = yaml.safe_load((HERE / "config" / "arm.yaml").read_text(encoding="utf-8"))
    s = cfg["sort"]
    log = Log(cfg)
    limits = {j["channel"]: (j["min"], j["max"]) for j in cfg["joints"].values()}
    g = cfg["gripper"]
    limits[g["channel"]] = (g["min"], g["max"])

    with Maestro(os.environ.get("PERRY_PORT", cfg["port"]), limits=limits) as m, TopCamera(cfg) as cam:
        for ch in limits:
            m.set_speed(ch, cfg["speed"]); m.set_acceleration(ch, cfg["acceleration"])
        gcfg = GraspCfg(**cfg["grasp"])
        ignored = []      # (x, y) de cubos que no se pueden o no se pudieron agarrar
        tries = {}        # intentos por posición aproximada
        done = pushes = 0

        def is_ignored(c):
            return any(hypot(c.x - x, c.y - y) <= s["same_cube_cm"] for x, y in ignored)

        def can_try(c):   # candidato: alcanzable, no ignorado y con contenedor para su color
            return reachable(cfg, c) and not is_ignored(c) and (a.to or cfg["containers"].get(c.color))

        for cycle in range(1, s["max_cycles"] + 1):
            cubes = look(cfg, m, cam, log, f"vista{cycle}")   # TODOS: también son obstáculos
            for c in cubes:
                if not is_ignored(c) and not reachable(cfg, c):
                    log(f"Cubo {c.color} en ({c.x:.1f}, {c.y:.1f}) está FUERA DE ALCANCE "
                        f"(r = {hypot(c.x, c.y):.1f} cm). Lo ignoro.")
                    ignored.append((c.x, c.y))
            if not any(can_try(c) for c in cubes):
                log(f"No quedan cubos alcanzables. Clasificados: {done}. Ignorados: {len(ignored)}.")
                break
            choice = choose_grasp(cubes, gcfg, can_try)
            if choice is None:
                plan = plan_push(cubes, gcfg, can_try, point_ok=lambda p: reachable(cfg, p))
                if plan is None or pushes >= s["max_pushes"]:
                    log("Hay cubos pero ninguno se puede agarrar ni separar empujando. Me detengo.")
                    break
                dx, dy = plan.direction
                log(f"Ciclo {cycle}: ningún cubo tiene un eje libre (bloque). Empujo el cubo en "
                    f"({plan.cube.x:.1f}, {plan.cube.y:.1f}) {gcfg.push:.1f} cm hacia ({dx:+.2f}, {dy:+.2f}).")
                if not a.run:
                    log("Modo prueba: no se mueve nada. Agrega --run."); break
                push(cfg, m, plan.start, plan.end, degrees(atan2(dy, dx)))
                pushes += 1
                continue
            c, grasp_dir = choice
            container = a.to or cfg["containers"][c.color]
            log(f"Ciclo {cycle}: cubo {c.color} en ({c.x:.1f}, {c.y:.1f}) girado {c.angle:+.0f}°, "
                f"cierro a {grasp_dir % 180:.0f}° -> {container}")
            if not a.run:
                log("Modo prueba: no se mueve nada. Agrega --run."); break
            try:
                pick(cfg, m, c, grasp_dir)
            except OutOfTable as e:
                log(f"No se puede llegar: {e}. Lo ignoro."); ignored.append((c.x, c.y)); continue
            # verificar: si sigue un cubo ahí, el agarre falló
            after = look(cfg, m, cam, log, f"verificacion{cycle}")
            still = [d for d in after if hypot(d.x - c.x, d.y - c.y) < s["same_cube_cm"]]
            if still:
                key = (round(c.x), round(c.y))
                tries[key] = tries.get(key, 0) + 1
                log(f"El agarre falló (intento {tries[key]}): el cubo sigue en ({still[0].x:.1f}, {still[0].y:.1f}).")
                if tries[key] > s["retries"]:
                    log("Lo doy por perdido."); ignored.append((c.x, c.y))
                g_ = cfg["gripper"]; m.set_us(g_["channel"], g_["open"]); m.wait()
                continue
            drop(cfg, m, container)
            done += 1
            log(f"Cubo {c.color} soltado en {container}. Llevo {done}.")
        move_via_top(m, cfg, cfg["poses"]["vista"], precise_base=False)
    log(f"Fin. Registro y fotos en {log.dir}")


if __name__ == "__main__":
    main()
