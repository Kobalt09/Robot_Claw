"""Llevar la pinza a un punto (x, y) de la mesa usando posturas enseñadas.

La pinza baja siempre igual, así que hombro, codo y muñeca dependen solo de la
distancia r al eje de la base. En arm.yaml (`reach`) hay una tabla de posturas
reales (r -> pulsos) y aquí se interpola entre filas. La base se calcula con su
calibración (ángulo -> pulso) y el giro con la de la muñeca giratoria.

Se usa en lugar de la cinemática para hombro, codo y muñeca porque medir esos
ángulos con fotos daba ±3° de error; una postura enseñada es exacta.

La base tiene juego mecánico (~7°): siempre se llega a su pulso desde abajo,
pasando antes por pulso - backlash_us.
"""
from math import atan2, degrees, hypot
import time

from kinematics import angle_to_us

ARM = ["hombro", "codo", "muneca"]


class OutOfTable(ValueError):
    pass


def interp_reach(cfg, r, level="grip"):
    """Pulsos de hombro, codo y muñeca para la distancia r (cm), interpolando la tabla."""
    rows = sorted(cfg["reach"]["rows"], key=lambda row: row["r"])
    r_max = min(rows[-1]["r"], cfg["reach"].get("max_r", rows[-1]["r"]))
    if not rows[0]["r"] <= r <= r_max:
        raise OutOfTable(f"r = {r:.1f} cm fuera de alcance [{rows[0]['r']}, {r_max}]")
    for lo, hi in zip(rows, rows[1:]):
        if lo["r"] <= r <= hi["r"]:
            t = (r - lo["r"]) / (hi["r"] - lo["r"]) if hi["r"] > lo["r"] else 0.0
            us = {j: lo[j] + t * (hi[j] - lo[j]) for j in ARM}
            break
    us["hombro"] += cfg["reach"].get("grip_shoulder_offset_us", 0)
    if level == "approach":
        us["hombro"] += cfg["reach"]["approach_shoulder_us"]
    return us


def pulses_at(cfg, x, y, cube_angle=0.0, level="grip", grasp_dir=None):
    """Pulsos de base, hombro, codo, muñeca y giro para dejar la pinza sobre (x, y).

    grasp_dir: dirección (grados, en la mesa) en que deben cerrar los dedos. Si se da, el giro
    va a [-90, 90) y permite elegir cualquiera de los dos ejes del cubo. Si no, se usa el eje
    del cubo más cercano (giro en [-45, 45]).
    """
    base = degrees(atan2(y, x))
    if grasp_dir is not None:
        # con giro 0 los dedos cierran perpendiculares al brazo (base + 90°); la pinza es simétrica cada 180°
        giro = ((grasp_dir - 90.0 - base + 90.0) % 180.0) - 90.0
    else:
        # el cubo es simétrico cada 90°: el giro relativo se lleva a [-45, 45]
        giro = ((cube_angle - base + 45) % 90) - 45
    us = interp_reach(cfg, hypot(x, y), level)
    us["base"] = angle_to_us(cfg["joints"]["base"], base)
    us["giro"] = angle_to_us(cfg["joints"]["giro"], giro)
    return us


def move_via_top(m, cfg, target, precise_base=True):
    """Va a `target` ({articulación: pulso}) pasando por arriba, de a una articulación.

    1) sube a la pose de traslado (hombro, codo, muñeca), 2) gira base y giro allá arriba,
    3) baja: primero codo y muñeca, el hombro al final. Así nunca barre contenedores ni cubos.
    precise_base=False gira la base directo (sin compensar el juego): sirve para contenedores
    y poses fijas, donde un ida y vuelta solo sacude el cubo.
    """
    ch = {j: cfg["joints"][j]["channel"] for j in cfg["joints"]}
    for j in ARM:
        m.set_us(ch[j], cfg["travel"][j]); m.wait()
    if "base" in target:
        if precise_base:
            set_base(m, cfg, target["base"])
        else:
            m.set_us(ch["base"], target["base"]); m.wait()
    for j in ("giro", "codo", "muneca"):
        if j in target:
            m.set_us(ch[j], target[j]); m.wait()
    if "hombro" in target:
        lower_shoulder(m, cfg, target["hombro"])


def push(m, cfg, start, end, direction):
    """Empuja cubos: baja la pinza CERRADA en `start` y la desliza hasta `end` sin subir.

    direction: dirección del empuje (grados). Los dedos cierran a lo largo de ella, así la pinza
    cerrada presenta su cara ancha al cubo. Avanza de a push_step_cm, todo el brazo a la vez.
    """
    g = cfg["gripper"]
    ch = {j: cfg["joints"][j]["channel"] for j in cfg["joints"]}
    lift = cfg["push_lift_us"]
    m.set_us(g["channel"], g["closed"]); m.wait()
    high = pulses_at(cfg, *start, level="approach", grasp_dir=direction)
    move_via_top(m, cfg, high)
    low = pulses_at(cfg, *start, level="grip", grasp_dir=direction)
    lower_shoulder(m, cfg, low["hombro"] + lift)
    dist = hypot(end[0] - start[0], end[1] - start[1])
    steps = max(1, int(dist / cfg["push_step_cm"]))
    # Juego de la base (~7°): se llegó al inicio subiendo el pulso. Si el empuje necesita BAJAR el
    # pulso, los primeros backlash_us solo recorren la holgura y el cubo no se mueve: se compensa.
    b0 = low["base"]
    b_end = pulses_at(cfg, *end, level="grip", grasp_dir=direction)["base"]
    slack = -cfg["joints"]["base"]["backlash_us"] if b_end < b0 else 0.0
    for i in range(1, steps + 1):
        t = i / steps
        x, y = start[0] + t * (end[0] - start[0]), start[1] + t * (end[1] - start[1])
        p = pulses_at(cfg, x, y, level="grip", grasp_dir=direction)
        p["hombro"] += lift
        p["base"] += slack
        for j in ("base", "giro", "codo", "muneca", "hombro"):
            m.set_us(ch[j], p[j])
        m.wait()
    for j, us in cfg["travel"].items():          # subir en vertical antes de cualquier giro
        m.set_us(ch[j], us); m.wait()


def lower_shoulder(m, cfg, us):
    """Mueve el hombro; si baja, lo hace lento para que el brazo estirado no caiga contra la mesa."""
    ch = cfg["joints"]["hombro"]["channel"]
    if us < m.get_us(ch):
        m.set_speed(ch, cfg["descent_speed"])
    m.set_us(ch, us); m.wait(timeout=15.0)
    m.set_speed(ch, cfg["speed"])


def set_base(m, cfg, us):
    """Mueve la base llegando siempre desde abajo, para que el juego quede igual."""
    ch = cfg["joints"]["base"]["channel"]
    m.set_us(ch, us - cfg["joints"]["base"]["backlash_us"])
    m.wait()
    m.set_us(ch, us)
    m.wait()


def is_energized(m, cfg):
    """Comprueba que todos los canales en arm.yaml (articulaciones y pinza) tengan pulsos (> 0 us).

    Devuelve False si algún servo lee 0 us (desenergizado tras encendido) o si la lectura falla.
    """
    try:
        channels = [j["channel"] for j in cfg.get("joints", {}).values()]
        if "gripper" in cfg and "channel" in cfg["gripper"]:
            channels.append(cfg["gripper"]["channel"])
        if not channels:
            return False
        for ch in channels:
            us = m.get_us(ch)
            if us is None or us <= 0:
                return False
        return True
    except Exception:
        return False


def is_parked(m, cfg, tol_us=None):
    """Comprueba que el brazo esté energizado, quieto y en la pose de reposo ('vista').

    Requisitos:
    1. is_energized(m, cfg) es True.
    2. not m.is_moving().
    3. Pulsos actuales de hombro, codo y muñeca coinciden con cfg['travel'] dentro de ±tol_us.
    4. Pulso actual de base coincide con cfg['poses']['vista']['base'] dentro de ±tol_us.
    """
    if tol_us is None:
        tol_us = cfg.get("park_tolerance_us", 30)

    try:
        if not is_energized(m, cfg):
            return False
        if m.is_moving():
            return False

        for j in ARM:
            ch = cfg["joints"][j]["channel"]
            target = cfg["travel"][j]
            current = m.get_us(ch)
            if abs(current - target) > tol_us:
                return False

        base_ch = cfg["joints"]["base"]["channel"]
        base_target = cfg["poses"]["vista"]["base"]
        base_current = m.get_us(base_ch)
        if abs(base_current - base_target) > tol_us:
            return False

        return True
    except Exception:
        return False


def ensure_parked(m, cfg):
    """Garantiza que el brazo esté en la pose de reposo ('vista').

    - Si is_energized() es False: no mueve nada (evita tirones bruscos) y devuelve False.
    - Si ya está estacionado (is_parked() == True): devuelve True sin mover nada.
    - Si está energizado pero fuera de lugar: ejecuta move_via_top a 'vista'
      (precise_base=False), espera estabilización y retorna is_parked().
    """
    if not is_energized(m, cfg):
        return False

    if is_parked(m, cfg):
        return True

    try:
        move_via_top(m, cfg, cfg["poses"]["vista"], precise_base=False)
        settle_s = cfg.get("park_settle_s", 0.0)
        if settle_s > 0:
            time.sleep(settle_s)
        return is_parked(m, cfg)
    except Exception:
        return False
