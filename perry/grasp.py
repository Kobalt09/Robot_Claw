"""Planificación de agarre para cubos agrupados (geometría pura: sin brazo ni cámara).

Los rastrillos dejan los cubos en filas o bloques. Un cubo se puede agarrar por un EJE
(los dos dedos cierran sobre dos caras opuestas) si en ambos lados de ese eje hay lugar para
que bajen los dedos. Cada cubo tiene dos ejes: su ángulo y su ángulo + 90°.

Huella de un dedo, a lo largo del eje y medida desde el centro del cubo:
  de  apertura/2 - error   (no más adentro que la cara del cubo)
  a   apertura/2 + grosor_dedo + error
y de ancho  ancho_dedo + 2·error.  El eje está libre si ninguna huella pisa otro cubo.

Si ningún cubo tiene un eje libre (p. ej. un bloque 2x2), se planifica un EMPUJE: la pinza
cerrada se apoya en una cara libre y desliza el cubo (y los que estén en línea con él) a lo
largo de la normal de esa cara, hasta que algún cubo quede agarrable.
Ejes: X hacia la zona, Y a la izquierda; ángulos en grados.
"""
from dataclasses import dataclass, replace
from math import atan2, cos, degrees, hypot, radians, sin


@dataclass
class Cube:
    color: str
    x: float
    y: float
    angle: float     # giro del cubo visto desde arriba (una de sus normales de cara)


@dataclass
class GraspCfg:
    cube: float          # lado del cubo (cm)
    finger_thick: float  # grosor de un dedo (cm)
    finger_width: float  # ancho de un dedo (cm)
    opening: float       # apertura de la pinza al bajar (cm)
    error: float         # error de posición esperado (cm)
    push: float          # cuánto se desliza un cubo al empujarlo (cm)
    eps: float = 0.05    # tolerancia: tocarse no es chocar
    w_giro: float = 0.3  # penalización por girar mucho la pinza
    w_r: float = 0.02    # penalización por distancia al eje
    push_dir_step: float = 0.0   # además de las 4 caras, probar empujes cada estos grados (0 = solo caras)


@dataclass
class PushPlan:
    cube: Cube
    direction: tuple     # (dx, dy) unitario
    start: tuple         # (x, y) donde baja la pinza cerrada
    end: tuple           # (x, y) hasta donde la desliza
    predicted: list      # posición esperada de todos los cubos después del empuje


def _rect(cx, cy, ang, half_u, half_v):
    """Rectángulo orientado: half_u a lo largo de `ang`, half_v perpendicular."""
    u, v = (cos(radians(ang)), sin(radians(ang))), (-sin(radians(ang)), cos(radians(ang)))
    return [(cx + su * half_u * u[0] + sv * half_v * v[0], cy + su * half_u * u[1] + sv * half_v * v[1])
            for su, sv in ((1, 1), (1, -1), (-1, -1), (-1, 1))]


def _overlap(a, b, eps):
    """Teorema del eje separador para dos rectángulos (convexos)."""
    for poly in (a, b):
        for i in range(4):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % 4]
            nx, ny = y1 - y2, x2 - x1
            pa = [nx * x + ny * y for x, y in a]
            pb = [nx * x + ny * y for x, y in b]
            n = hypot(nx, ny)
            if min(max(pa), max(pb)) - max(min(pa), min(pb)) <= eps * n:
                return False
    return True


def _square(c, g):
    return _rect(c.x, c.y, c.angle, g.cube / 2, g.cube / 2)


def closing_dirs(c):
    """Las dos direcciones en que pueden cerrar los dedos sobre caras opuestas."""
    return [c.angle, c.angle + 90.0]


def _fingers(c, direction, g, extra=0.0):
    inner = max(g.cube / 2, g.opening / 2 - g.error)
    outer = g.opening / 2 + g.finger_thick + g.error + extra
    mid, half_u, half_v = (inner + outer) / 2, (outer - inner) / 2, g.finger_width / 2 + g.error + extra
    u = (cos(radians(direction)), sin(radians(direction)))
    return [_rect(c.x + s * mid * u[0], c.y + s * mid * u[1], direction, half_u, half_v) for s in (1, -1)]


def finger_boxes(c, direction, g):
    """Las 2 huellas de los dedos (rectángulos en cm, con el margen de error) para auditar."""
    return _fingers(c, direction, g)


def axis_is_free(c, others, direction, g, extra=0.0):
    fingers = _fingers(c, direction, g, extra)
    return not any(_overlap(f, _square(o, g), g.eps) for f in fingers for o in others if o is not c)


def axis_clearance(c, others, direction, g, cap=2.0):
    """Holgura extra (cm) que queda alrededor de los dedos; -1 si el eje no está libre."""
    if not axis_is_free(c, others, direction, g):
        return -1.0
    lo, hi = 0.0, cap
    for _ in range(12):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if axis_is_free(c, others, direction, g, mid) else (lo, mid)
    return lo


def relative_giro(c, direction):
    """Giro de pinza (grados, en [-90, 90)) para cerrar en `direction`, ya restada la base."""
    base = degrees(atan2(c.y, c.x))
    return (direction - 90.0 - base + 90.0) % 180.0 - 90.0


def choose_grasp(cubes, g, reachable):
    """El agarre más conveniente: (cubo, dirección de cierre) o None si no hay ninguno."""
    best, best_score = None, None
    for c in cubes:
        if not reachable(c):
            continue
        for d in closing_dirs(c):
            clear = axis_clearance(c, cubes, d, g)
            if clear < 0:
                continue
            score = clear - g.w_giro * abs(relative_giro(c, d)) / 90.0 - g.w_r * hypot(c.x, c.y)
            if best_score is None or score > best_score:
                best, best_score = (c, d), score
    return best


def push_dirs(c, g):
    """Direcciones (grados) en que se prueba empujar un cubo: sus 4 caras y, si push_dir_step > 0,
    cualquier ángulo cada push_dir_step (el cubo se desliza y gira algo; después se vuelve a mirar)."""
    dirs = [c.angle + 90.0 * k for k in range(4)]
    if g.push_dir_step > 0:
        dirs += [k * g.push_dir_step for k in range(int(round(360 / g.push_dir_step)))]
    return dirs


def _slide(cubes, first, n, g):
    """Cubos que se mueven si se empuja `first` en la dirección n (los que están en línea)."""
    moved, frontier = {id(first)}, [first]
    while frontier:
        c = frontier.pop()
        swept = _rect(c.x + n[0] * g.push / 2, c.y + n[1] * g.push / 2,
                      degrees(atan2(n[1], n[0])), g.cube / 2 + g.push / 2, g.cube / 2)
        for o in cubes:
            if id(o) not in moved and _overlap(swept, _square(o, g), g.eps):
                moved.add(id(o)); frontier.append(o)
    return [replace(o, x=o.x + n[0] * g.push, y=o.y + n[1] * g.push) if id(o) in moved else o for o in cubes], len(moved)


def plan_push(cubes, g, reachable, point_ok=None):
    """Si nada es agarrable, el empuje más simple que deja algún cubo agarrable (o None).

    reachable(cubo): si el cubo es candidato (para empujar y para agarrar después).
    point_ok(cubo):  si una posición está al alcance del brazo (dónde baja el empujador y dónde
                     quedan los cubos empujados). Por defecto, igual que reachable.
    """
    point_ok = point_ok or reachable
    if choose_grasp(cubes, g, reachable) is not None:
        return None
    best, best_key = None, None
    half = g.finger_thick              # pinza cerrada: dos dedos juntos, ~2 grosores
    for c in cubes:
        if not reachable(c):
            continue
        for a in push_dirs(c, g):
            n = (cos(radians(a)), sin(radians(a)))
            t = radians(a - c.angle)    # distancia del centro al borde del cubo en esa dirección
            back = g.cube / 2 * (abs(cos(t)) + abs(sin(t))) + half + g.error
            start = (c.x - n[0] * back, c.y - n[1] * back)
            pusher = _rect(start[0], start[1], a, half + g.error, g.finger_width / 2 + g.error)
            if any(_overlap(pusher, _square(o, g), g.eps) for o in cubes):
                continue                    # no hay lugar para bajar la pinza de ese lado
            travel = g.push + g.error       # primero cierra la luz, después mueve el cubo g.push
            end = (start[0] + n[0] * travel, start[1] + n[1] * travel)
            predicted, n_moved = _slide(cubes, c, n, g)
            moved_ok = all(point_ok(p) for p, o in zip(predicted, cubes) if p is not o)
            if not moved_ok or not point_ok(Cube("", *start, a)) or not point_ok(Cube("", *end, a)):
                continue
            if choose_grasp(predicted, g, reachable) is not None:
                key = (0, n_moved, hypot(*start))                    # ideal: deja algo agarrable
            else:
                key = (1, -_freedom(predicted, g, reachable), hypot(*start))   # mejor esfuerzo
            if best_key is None or key < best_key:
                best, best_key = PushPlan(c, n, start, end, predicted), key
    return best


def grab_succeeded(before, after, target):
    """¿Se levantó el cubo? Solo si ahora hay UNO MENOS de su color en la zona.

    No alcanza con "ya no está en el mismo lugar": un agarre fallido puede empujar el cubo
    más allá de cualquier radio y parecer un éxito (pasó el 27-10 a 19,4 cm del eje).
    """
    count = lambda cubes: sum(1 for c in cubes if c.color == target.color)  # noqa: E731
    return count(after) < count(before)


def _freedom(cubes, g, reachable):
    """Qué tan 'suelto' está el grupo: suma de la mejor holgura de cada cubo (bloqueado = -1).
    Sirve para elegir un empuje cuando ninguno deja algo agarrable en la simulación: el empuje
    real no es una simulación perfecta, así que se empuja, se vuelve a mirar y se itera."""
    return sum(max(axis_clearance(c, cubes, d, g) for d in closing_dirs(c)) for c in cubes if reachable(c))
