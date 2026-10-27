"""Cinemática inversa geométrica de Perry (método de la tesis de Lugo, 2023).

Convenciones (las mismas de la calibración):
- Origen en el eje de giro de la base, sobre la mesa. X hacia la zona, Y a la izquierda, Z arriba.
- base:   0° sobre el eje X, positivo hacia la izquierda.
- hombro: ángulo entre la horizontal y el primer eslabón (90° = vertical).
- codo:   ángulo interior entre brazo y antebrazo (180° = recto).
- muneca: ángulo interior entre antebrazo y pinza (180° = recto).
- giro:   giro de la pinza; 0° = dedos cerrando de izquierda a derecha.
La pinza baja siempre vertical.
"""
from math import atan2, acos, hypot, degrees


class OutOfReach(ValueError):
    pass


def inverse_kinematics(x, y, z, links, cube_angle=0.0):
    E1, E2, E3, E45 = links["E1"], links["E2"], links["E3"], links["E45"]
    t1 = atan2(y, x)
    r = hypot(x, y)
    a = (z + E45) - E1
    c = hypot(r, a)
    if not abs(E3 - E2) <= c <= E2 + E3:
        raise OutOfReach(f"punto ({x:.1f}, {y:.1f}) fuera de alcance: c = {c:.1f} cm, máximo {E2 + E3:.1f}")
    t2 = atan2(a, r) + acos((c * c + E2 * E2 - E3 * E3) / (2 * c * E2))
    t3 = acos((E2 * E2 + E3 * E3 - c * c) / (2 * E2 * E3))
    t4 = atan2(r, a) + acos((c * c + E3 * E3 - E2 * E2) / (2 * c * E3))
    base = degrees(t1)
    # el cubo es simétrico cada 90°: se lleva el giro relativo a [-45, 45]
    giro = ((cube_angle - base + 45) % 90) - 45
    return {"base": base, "hombro": degrees(t2), "codo": degrees(t3), "muneca": degrees(t4), "giro": giro}


def angle_to_us(joint, deg):
    """Interpola en línea recta entre los puntos de calibración [ángulo, pulso] del servo.

    Con dos puntos es una recta. Con más, se interpola por tramos (sirve si el servo no es
    lineal); fuera del rango se prolonga el tramo más cercano.
    """
    cal = sorted(joint["cal"])
    if any(p is None for _, p in cal):
        raise ValueError("falta calibrar este servo (pulsos en arm.yaml)")
    i = 1
    while i < len(cal) - 1 and deg > cal[i][0]:
        i += 1
    (a1, p1), (a2, p2) = cal[i - 1], cal[i]
    return p1 + (deg - a1) * (p2 - p1) / (a2 - a1)
