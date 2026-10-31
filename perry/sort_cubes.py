"""Perry clasifica solo: ve los cubos de la zona y los lleva a su contenedor.

  py sort_cubes.py              -> solo mira: lista los cubos y qué haría (no mueve nada)
  py sort_cubes.py --run        -> ciclo completo hasta vaciar la zona
  py sort_cubes.py --run --to amarillo   -> todo al mismo contenedor (pruebas)
También se maneja desde la interfaz web: py audit_web.py (botones Iniciar / Cancelar).

Ciclo por cubo: estacionar (para no tapar la cámara) -> detectar -> decidir (planner.py) ->
agarrar por arriba con la pinza girada al eje libre, o empujar un grupo bloqueado ->
verificar contando cubos -> contenedor de su color -> soltar.

Reglas para que funcione sin nadie al lado:
- un cubo fuera de alcance no se intenta: se avisa y se ignora;
- si el agarre falla, se reintenta (sort.retries) y luego se ignora ese cubo;
- todo se registra con hora y foto (incluida la imagen de planificación) en perry/logs/.
Puerto: variable PERRY_PORT (en Windows, por ejemplo COM5) o el de arm.yaml.
"""
import argparse
import os
import threading
import time
from math import atan2, degrees, hypot
from pathlib import Path

import yaml

from audit import draw_plan
from grasp import GraspCfg, grab_succeeded
from maestro import Maestro
from planner import decide
from reach import pulses_at, move_via_top, lower_shoulder, push, OutOfTable
from vision import TopCamera, save_image

HERE = Path(__file__).parent


class Cancelled(Exception):
    pass


class Log:
    """Registro en archivo + pantalla. sink(línea) e image_sink(nombre, img) son opcionales (web)."""

    def __init__(self, cfg, sink=None, image_sink=None):
        self.dir = HERE / cfg["sort"]["log_dir"] / time.strftime("%Y-%m-%d_%H-%M-%S")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file = open(self.dir / "registro.txt", "a", encoding="utf-8")
        self.sink, self.image_sink = sink, image_sink

    def __call__(self, msg):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line)
        self.file.write(line + "\n"); self.file.flush()
        if self.sink:
            self.sink(line)

    def image(self, name, img):
        if not save_image(self.dir / f"{time.strftime('%H-%M-%S')}_{name}.jpg", img):
            self(f"[aviso] no se pudo guardar la foto {name}")
        if self.image_sink:
            self.image_sink(name, img)


def open_arm(cfg):
    limits = {j["channel"]: (j["min"], j["max"]) for j in cfg["joints"].values()}
    g = cfg["gripper"]
    limits[g["channel"]] = (g["min"], g["max"])
    m = Maestro(os.environ.get("PERRY_PORT", cfg["port"]), limits=limits)
    for ch in limits:
        m.set_speed(ch, cfg["speed"]); m.set_acceleration(ch, cfg["acceleration"])
    return m


def go_up(cfg, m):
    for j, us in cfg["travel"].items():
        m.set_us(cfg["joints"][j]["channel"], us); m.wait()


def look(cfg, m, cam, log, tag):
    """Estaciona el brazo fuera de la vista y devuelve los cubos de la zona (y la imagen)."""
    move_via_top(m, cfg, cfg["poses"]["vista"], precise_base=False)
    time.sleep(0.5)  # que se quede quieto antes de la foto
    cubes, img = cam.find_cubes()
    log.image(tag, img)
    return cubes, img


def pick(cfg, m, cube, grasp_dir, check):
    """Agarra el cubo cerrando en `grasp_dir` y lo deja arriba, en la pose de traslado."""
    g = cfg["gripper"]
    high = pulses_at(cfg, cube.x, cube.y, level="approach", grasp_dir=grasp_dir)
    low = pulses_at(cfg, cube.x, cube.y, level="grip", grasp_dir=grasp_dir)
    m.set_us(g["channel"], g["open"]); m.wait(); check()
    move_via_top(m, cfg, high); check()            # por arriba, base precisa, pinza girada
    lower_shoulder(m, cfg, low["hombro"])           # baja lento
    m.set_us(g["channel"], g["closed"]); m.wait(); time.sleep(0.3)
    go_up(cfg, m)                                   # sube en vertical primero con el hombro


def drop(cfg, m, container):
    g = cfg["gripper"]
    move_via_top(m, cfg, cfg["poses"][container], precise_base=False)
    m.set_us(g["channel"], g["open"]); m.wait(); time.sleep(0.3)
    go_up(cfg, m)


def sort_loop(cfg, m, cam, log, run=True, to=None, stop=None, status=None, approve=None):
    """El ciclo completo. stop: threading.Event para cancelar; status(texto): estado actual.
    approve(texto): si se da, se llama antes de cada acción y bloquea hasta que el usuario la
    apruebe (modo paso a paso); si mientras tanto se cancela, el ciclo termina."""
    s = cfg["sort"]
    gcfg = GraspCfg(**cfg["grasp"])
    stop = stop or threading.Event()
    say = status or (lambda t: None)

    def check():
        if stop.is_set():
            raise Cancelled()

    ignored, tries, done, pushes = [], {}, 0, 0
    try:
        for cycle in range(1, s["max_cycles"] + 1):
            check()
            say(f"Ciclo {cycle}: mirando la zona")
            cubes, img = look(cfg, m, cam, log, f"vista{cycle}")   # TODOS: también son obstáculos
            dec = decide(cfg, cubes, ignored, to)
            log.image(f"plan{cycle}", draw_plan(img, cam, cfg, cubes, dec))   # para auditar
            for c in dec.unreachable:
                log(f"Cubo {c.color} en ({c.x:.1f}, {c.y:.1f}) está FUERA DE ALCANCE "
                    f"(r = {hypot(c.x, c.y):.1f} cm). Lo ignoro.")
                ignored.append((c.x, c.y))
            if dec.kind == "none":
                log(f"{dec.message} Clasificados: {done}. Ignorados: {len(ignored)}.")
                break
            check()
            if dec.kind == "push":
                if pushes >= s["max_pushes"]:
                    log(f"Empujé {pushes} veces seguidas sin poder agarrar nada: ZONA BLOQUEADA. Me detengo.")
                    break
                plan = dec.plan
                dx, dy = plan.direction
                log(f"Ciclo {cycle}: ningún cubo tiene un eje libre (bloque). Empujo el cubo en "
                    f"({plan.cube.x:.1f}, {plan.cube.y:.1f}) {gcfg.push:.1f} cm hacia ({dx:+.2f}, {dy:+.2f}).")
                if not run:
                    log("Modo prueba: no se mueve nada."); break
                if approve:
                    say(f"ESPERANDO TU APROBACION: {dec.message}"); approve(); check()
                say(f"Ciclo {cycle}: empujando un grupo")
                push(m, cfg, plan.start, plan.end, degrees(atan2(dy, dx)))
                pushes += 1
                continue
            c, grasp_dir = dec.cube, dec.grasp_dir
            container = to or cfg["containers"][c.color]
            log(f"Ciclo {cycle}: cubo {c.color} en ({c.x:.1f}, {c.y:.1f}) girado {c.angle:+.0f}°, "
                f"cierro a {grasp_dir % 180:.0f}° -> {container}")
            if not run:
                log("Modo prueba: no se mueve nada."); break
            if approve:
                say(f"ESPERANDO TU APROBACION: {dec.message}"); approve(); check()
            say(f"Ciclo {cycle}: agarrando cubo {c.color} en ({c.x:.1f}, {c.y:.1f})")
            try:
                pick(cfg, m, c, grasp_dir, check)
            except OutOfTable as e:
                log(f"No se puede llegar: {e}. Lo ignoro."); ignored.append((c.x, c.y)); continue
            say(f"Ciclo {cycle}: verificando el agarre")
            after, _ = look(cfg, m, cam, log, f"verificacion{cycle}")   # verificar CONTANDO
            if not grab_succeeded(cubes, after, c):
                # el mismo cubo = el intento anterior más cercano (un agarre fallido lo corre unos mm)
                key = next((k for k in tries if hypot(k[0] - c.x, k[1] - c.y) < 2 * s["same_cube_cm"]), (c.x, c.y))
                tries[key] = tries.get(key, 0) + 1
                near = min(after, key=lambda d: hypot(d.x - c.x, d.y - c.y), default=None)
                where = f" (el más cercano quedó en ({near.x:.1f}, {near.y:.1f}))" if near else ""
                log(f"El agarre falló (intento {tries[key]}): sigue habiendo "
                    f"{sum(d.color == c.color for d in after)} cubo(s) {c.color}{where}.")
                if tries[key] > s["retries"]:
                    log("Lo doy por perdido."); ignored.append((c.x, c.y))
                g_ = cfg["gripper"]; m.set_us(g_["channel"], g_["open"]); m.wait()
                continue
            check()
            say(f"Ciclo {cycle}: llevando el cubo {c.color} a {container}")
            drop(cfg, m, container)
            done += 1
            pushes = 0   # el límite de empujes es por atasco: si se agarró algo, la situación cambió
            log(f"Cubo {c.color} soltado en {container}. Llevo {done}.")
    except Cancelled:
        log("CANCELADO por el usuario: subo y estaciono el brazo.")
        go_up(cfg, m)
    move_via_top(m, cfg, cfg["poses"]["vista"], precise_base=False)
    say("Detenido")
    log(f"Fin. Clasificados: {done}. Registro y fotos en {log.dir}")
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="mover el brazo (sin esto solo mira)")
    ap.add_argument("--to", help="mandar todos los cubos a este contenedor (pruebas)")
    a = ap.parse_args()
    cfg = yaml.safe_load((HERE / "config" / "arm.yaml").read_text(encoding="utf-8"))
    m = open_arm(cfg)
    try:
        with TopCamera(cfg) as cam:
            sort_loop(cfg, m, cam, Log(cfg), run=a.run, to=a.to)
    finally:
        m.close()


if __name__ == "__main__":
    main()
