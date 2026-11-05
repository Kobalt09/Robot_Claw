"""Qué hacer con los cubos que se ven: agarrar uno, empujar un grupo o nada.

Lo usan sort_cubes.py (el ciclo real) y audit.py (la interfaz para auditar), así la interfaz
muestra exactamente la misma decisión que tomaría el brazo.
"""
from dataclasses import dataclass, field
from math import hypot

from grasp import GraspCfg, axis_clearance, blocked_behind, choose_grasp, closing_dirs, plan_push


def reachable(cfg, c):
    """Dentro del rango de la tabla enseñada y del límite duro reach.max_r."""
    rows = cfg["reach"]["rows"]
    r = hypot(c.x, c.y)
    r_max = min(max(row["r"] for row in rows), cfg["reach"].get("max_r", 99))
    return min(row["r"] for row in rows) <= r <= r_max


def sortable(cfg, c, to=None, colors=None):
    """¿Es un cubo para clasificar? Tiene caja (o hay destino forzado) y es del color pedido.
    Los demás (el rojo, o los colores que el operador no eligió) son solo obstáculos."""
    return bool(to or cfg["containers"].get(c.color)) and (not colors or c.color in colors)


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
    box: str = None                 # adónde va el cubo agarrado: una caja o "descarte"


def decide(cfg, cubes, ignored=(), to=None, colors=None):
    """Decide la próxima acción. ignored: posiciones (x, y) que ya no se intentan.
    colors: si se da, solo se agarran (o empujan) cubos de esos colores; los demás quedan como obstáculos."""
    s, g = cfg["sort"], GraspCfg(**cfg["grasp"])

    def is_ignored(c):
        return any(hypot(c.x - x, c.y - y) <= s["same_cube_cm"] for x, y in ignored)

    def can_try(c):   # candidato: alcanzable, no ignorado y para clasificar
        return reachable(cfg, c) and not is_ignored(c) and sortable(cfg, c, to, colors)

    def can_discard(c):   # cubo sin caja (rojo) que se puede sacar de la zona; no si el operador eligió un color
        return (not colors and c.color in s.get("discard_colors", ()) and reachable(cfg, c) and not is_ignored(c))

    def discard(c, d, why):
        return Decision("grab", c, d, unreachable=unreachable, box="descarte",
                        message=f"DESCARTAR el cubo {c.color} en ({c.x:.1f}, {c.y:.1f}) ({why})")

    def push_to_free(candidate):
        """Empuje que deja algún `candidate` agarrable (o None)."""
        # un empuje en cadena corre los cubos unos mm más de lo previsto: margen en AMBOS bordes del alcance
        r_lo = min(row["r"] for row in cfg["reach"]["rows"]) + s["push_margin_r"]
        r_hi = cfg["reach"]["max_r"] - s["push_margin_r"]
        arm_ok = lambda p: reachable(cfg, p) and in_zone(cfg, p)                   # noqa: E731  donde puede bajar la pinza
        cube_ok = lambda p: arm_ok(p) and r_lo <= hypot(p.x, p.y) <= r_hi         # noqa: E731  donde pueden quedar cubos
        plan = plan_push(cubes, g, candidate, point_ok=arm_ok, cube_ok=cube_ok)
        if plan is None:
            return None
        moved = sum(1 for a, b in zip(cubes, plan.predicted) if (a.x, a.y) != (b.x, b.y))
        return Decision("push", plan.cube, plan=plan, unreachable=unreachable,
                        message=f"EMPUJAR el cubo {plan.cube.color} en ({plan.cube.x:.1f}, {plan.cube.y:.1f}) "
                                f"{direction_words(*plan.direction)}, {g.push:.1f} cm"
                                + (f" (arrastra {moved} cubos)" if moved > 1 else ""))

    unreachable = [c for c in cubes if not is_ignored(c) and not reachable(cfg, c) and sortable(cfg, c, to, colors)]
    if not any(can_try(c) for c in cubes):
        leftover = choose_grasp(cubes, g, can_discard)   # sin objetivos: limpiar la zona
        if leftover:
            return discard(*leftover, "limpiar la zona")
        if any(can_discard(c) for c in cubes):          # rojos pegados entre sí: separarlos para sacarlos
            pushed = push_to_free(can_discard)
            if pushed:
                return pushed
        which = f" de color {' o '.join(colors)}" if colors else ""
        return Decision("none", unreachable=unreachable, message=f"No quedan cubos{which} alcanzables.")
    choice = choose_grasp(cubes, g, can_try)
    if choice:
        c, d = choice
        box = to or cfg["containers"].get(c.color)
        return Decision("grab", c, d, unreachable=unreachable, box=box,
                        message=f"AGARRAR el cubo {c.color} en ({c.x:.1f}, {c.y:.1f}) y llevarlo a la caja {box}")
    # ningún objetivo se puede agarrar: sacar el rojo que más ayude (el que, al irse, deja un objetivo libre)
    reds = [(c, d) for c in cubes if can_discard(c) and not blocked_behind(c, cubes, g) for d in closing_dirs(c)
            if axis_clearance(c, cubes, d, g) >= 0]
    if reds:
        helps = [(c, d) for c, d in reds if choose_grasp([k for k in cubes if k is not c], g, can_try)]
        c, d = (helps or reds)[0]
        return discard(c, d, "tapa un cubo" if helps else "abre lugar")
    # se empujan objetivos o rojos: separar un rojo también abre lugar (y después se lo descarta)
    pushed = push_to_free(lambda c: can_try(c) or can_discard(c))
    return pushed or Decision("none", unreachable=unreachable,
                              message="Hay cubos, pero ninguno se puede agarrar ni separar empujando.")
