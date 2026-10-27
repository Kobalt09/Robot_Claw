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

from kinematics import angle_to_us

ARM = ["hombro", "codo", "muneca"]


class OutOfTable(ValueError):
    pass


def interp_reach(cfg, r, level="grip"):
    """Pulsos de hombro, codo y muñeca para la distancia r (cm), interpolando la tabla."""
    rows = sorted(cfg["reach"]["rows"], key=lambda row: row["r"])
    if not rows[0]["r"] <= r <= rows[-1]["r"]:
        raise OutOfTable(f"r = {r:.1f} cm fuera de la tabla enseñada [{rows[0]['r']}, {rows[-1]['r']}]")
    for lo, hi in zip(rows, rows[1:]):
        if lo["r"] <= r <= hi["r"]:
            t = (r - lo["r"]) / (hi["r"] - lo["r"]) if hi["r"] > lo["r"] else 0.0
            us = {j: lo[j] + t * (hi[j] - lo[j]) for j in ARM}
            break
    us["hombro"] += cfg["reach"].get("grip_shoulder_offset_us", 0)
    if level == "approach":
        us["hombro"] += cfg["reach"]["approach_shoulder_us"]
    return us


def pulses_at(cfg, x, y, cube_angle=0.0, level="grip"):
    """Pulsos de base, hombro, codo, muñeca y giro para dejar la pinza sobre (x, y)."""
    base = degrees(atan2(y, x))
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
