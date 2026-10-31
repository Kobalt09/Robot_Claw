"""Qué hacer con los cubos que se ven: agarrar uno, empujar un grupo o nada.

Lo usan sort_cubes.py (el ciclo real) y audit.py (la interfaz para auditar), así la interfaz
muestra exactamente la misma decisión que tomaría el brazo.
"""
from dataclasses import dataclass, field
from math import hypot

from grasp import GraspCfg, choose_grasp, plan_push


def reachable(cfg, c):
    """Dentro del rango de la tabla enseñada y del límite duro reach.max_r."""
    rows = cfg["reach"]["rows"]
    r = hypot(c.x, c.y)
    r_max = min(max(row["r"] for row in rows), cfg["reach"].get("max_r", 99))
    return min(row["r"] for row in rows) <= r <= r_max


def in_zone(cfg, p):
    z = cfg["camera"]["zone"]
    return z["x_min"] <= p.x <= z["x_max"] and abs(p.y) <= z["y_abs"]


def direction_words(dx, dy):
    """Dirección en palabras, vista desde detrás del brazo mirando la zona (X lejos, Y izquierda)."""
    side = "hacia la izquierda" if dy > 0.38 else "hacia la derecha" if dy < -0.38 else ""
    depth = "alejándose de la base" if dx > 0.38 else "hacia la base" if dx < -0.38 else ""
    return " y ".join(w for w in (side, depth) if w)


@dataclass
class Decision:
    kind: str                       # "grab", "push" o "none"
    cube: object = None             # cubo a agarrar (grab) o a empujar (push)
    grasp_dir: float = None         # dirección de cierre de los dedos (grab)
    plan: object = None             # PushPlan (push)
    unreachable: list = field(default_factory=list)   # cubos fuera de alcance vistos ahora
    message: str = ""


def decide(cfg, cubes, ignored=(), to=None):
    """Decide la próxima acción. ignored: posiciones (x, y) que ya no se intentan."""
    s, g = cfg["sort"], GraspCfg(**cfg["grasp"])

    def is_ignored(c):
        return any(hypot(c.x - x, c.y - y) <= s["same_cube_cm"] for x, y in ignored)

    def can_try(c):   # candidato: alcanzable, no ignorado y con contenedor para su color
        return reachable(cfg, c) and not is_ignored(c) and bool(to or cfg["containers"].get(c.color))

    unreachable = [c for c in cubes if not is_ignored(c) and not reachable(cfg, c)]
    if not any(can_try(c) for c in cubes):
        return Decision("none", unreachable=unreachable, message="No quedan cubos alcanzables.")
    choice = choose_grasp(cubes, g, can_try)
    if choice:
        c, d = choice
        box = to or cfg["containers"].get(c.color)
        return Decision("grab", c, d, unreachable=unreachable,
                        message=f"AGARRAR el cubo {c.color} en ({c.x:.1f}, {c.y:.1f}) y llevarlo a la caja {box}")
    margin = cfg["reach"]["max_r"] - s["push_margin_r"]
    arm_ok = lambda p: reachable(cfg, p) and in_zone(cfg, p)                       # noqa: E731  donde puede bajar la pinza
    cube_ok = lambda p: arm_ok(p) and hypot(p.x, p.y) <= margin                   # noqa: E731  donde pueden quedar cubos
    plan = plan_push(cubes, g, can_try, point_ok=arm_ok, cube_ok=cube_ok)
    if plan is None:
        return Decision("none", unreachable=unreachable,
                        message="Hay cubos, pero ninguno se puede agarrar ni separar empujando.")
    moved = sum(1 for a, b in zip(cubes, plan.predicted) if (a.x, a.y) != (b.x, b.y))
    return Decision("push", plan.cube, plan=plan, unreachable=unreachable,
                    message=f"EMPUJAR el cubo {plan.cube.color} en ({plan.cube.x:.1f}, {plan.cube.y:.1f}) "
                            f"{direction_words(*plan.direction)}, {g.push:.1f} cm"
                            + (f" (arrastra {moved} cubos)" if moved > 1 else ""))
