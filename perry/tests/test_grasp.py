"""Tests de la planificación de agarre (geometría pura, sin brazo ni cámara).

Medidas reales: cubo 1,9 cm; dedo 0,5 cm de grosor y 1,9 cm de ancho; pinza pre-cerrada a 2,9 cm.
Ejes: X hacia la zona, Y a la izquierda. Un cubo "girado 0°" tiene caras paralelas a X e Y.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from grasp import Cube, GraspCfg, axis_is_free, choose_grasp, plan_push, closing_dirs, grab_succeeded  # noqa: E402

G = GraspCfg(cube=1.9, finger_thick=0.5, finger_width=1.9, opening=2.9, error=0.5, push=3.0)
ALWAYS = lambda c: True  # todo alcanzable  # noqa: E731


def row_x(n, x0=14.0, y=0.0, gap=0.0):
    """n cubos en fila a lo largo de X, tocándose (gap = separación entre caras)."""
    return [Cube("azul", x0 + i * (1.9 + gap), y, 0.0) for i in range(n)]


def test_closing_dirs_are_both_face_normals():
    assert sorted(closing_dirs(Cube("azul", 15, 0, 10.0))) == [10.0, 100.0]


def test_isolated_cube_has_both_axes_free():
    c = Cube("azul", 15, 0, 0)
    assert axis_is_free(c, [], 0.0, G) and axis_is_free(c, [], 90.0, G)


def test_neighbors_along_x_block_x_axis_but_not_y():
    left, mid, right = row_x(3)
    others = [left, right]
    assert not axis_is_free(mid, others, 0.0, G)      # dedos en las caras que dan a los vecinos
    assert axis_is_free(mid, others, 90.0, G)         # dedos en las caras libres (Y)


def test_far_enough_neighbor_does_not_block():
    a, b = row_x(2, gap=2.0)                          # 2 cm entre caras > 0,5 + 0,5 + 0,5 necesarios
    assert axis_is_free(a, [b], 0.0, G)


def test_rotated_row_uses_rotated_axes():
    import math
    t = math.radians(30)
    cubes = [Cube("azul", 15 + i * 1.9 * math.cos(t), i * 1.9 * math.sin(t), 30.0) for i in range(3)]
    mid, others = cubes[1], [cubes[0], cubes[2]]
    assert not axis_is_free(mid, others, 30.0, G)
    assert axis_is_free(mid, others, 120.0, G)


def block_2x2(x0=14.0, y0=0.0):
    s = 1.9
    return [Cube("azul", x0, y0, 0), Cube("azul", x0 + s, y0, 0), Cube("azul", x0, y0 + s, 0), Cube("azul", x0 + s, y0 + s, 0)]


def test_2x2_block_has_no_graspable_cube():
    assert choose_grasp(block_2x2(), G, ALWAYS) is None


def test_choose_grasp_picks_free_axis_in_a_row():
    pick = choose_grasp(row_x(3), G, ALWAYS)
    assert pick is not None
    _, closing = pick
    assert closing % 180 == pytest.approx(90.0)       # cierra en Y: las caras libres


def test_choose_grasp_skips_unreachable():
    near, far = Cube("azul", 14, 0, 0), Cube("azul", 25, 0, 0)
    pick = choose_grasp([far, near], G, lambda c: c.x < 20)
    assert pick is not None and pick[0] is near


def test_push_on_2x2_pushes_along_a_face_normal_from_a_free_side():
    cubes = block_2x2()
    plan = plan_push(cubes, G, ALWAYS)
    assert plan is not None
    dx, dy = plan.direction
    assert abs(dx) < 1e-9 or abs(dy) < 1e-9                 # a lo largo de una normal de cara
    # el empujador arranca afuera del bloque: no pisa ningún cubo
    assert not any(abs(plan.start[0] - c.x) < 1.9 and abs(plan.start[1] - c.y) < 1.9 for c in cubes)
    # recorre la luz inicial (error) + el empuje: así el cubo se mueve exactamente G.push
    assert ((plan.end[0] - plan.start[0]) ** 2 + (plan.end[1] - plan.start[1]) ** 2) ** 0.5 == pytest.approx(G.push + G.error)


def test_push_never_moves_cubes_out_of_the_zone():
    # bloque pegado al borde izquierdo de la zona (|y| <= 9.5): no puede empujar hacia +y
    cubes = block_2x2(x0=14.0, y0=6.5)
    inside = lambda c: abs(c.y) <= 9.5 and 10 <= c.x <= 21  # noqa: E731
    plan = plan_push(cubes, G, ALWAYS, point_ok=inside)
    assert plan is not None
    assert all(inside(c) for c in plan.predicted)


def brick(x0=13.0, y0=0.0):
    """Pizarrón: 3 arriba y 2 abajo, corridos medio cubo (aparejo de ladrillos)."""
    s = 1.9
    top = [Cube("azul", x0 + s, y0 + (i - 1) * s, 0) for i in range(3)]
    bottom = [Cube("azul", x0, y0 + (i - 0.5) * s, 0) for i in range(2)]
    return top + bottom


def test_messy_cluster_still_gets_a_best_effort_push():
    # como en la foto tras un empuje real: bloque escalonado y girado, sin eje libre
    s = 1.9
    cubes = [Cube("azul", 14.0, 0.2, 5), Cube("azul", 14.0 + s, -0.4, -3), Cube("azul", 14.3, 0.2 + s, 8),
             Cube("azul", 14.0 + s, s - 0.6, 2), Cube("azul", 15.1, 2 * s + 0.1, 4)]
    if choose_grasp(cubes, G, ALWAYS) is None:
        plan = plan_push(cubes, G, ALWAYS)
        assert plan is not None


def test_grab_succeeded_when_one_cube_less():
    before = [Cube("azul", 15, 0, 0), Cube("azul", 17, 2, 0)]
    after = [Cube("azul", 17, 2, 0)]
    assert grab_succeeded(before, after, before[0])


def test_pushed_cube_is_not_a_success():
    # caso real del 27-10: la pinza empujó el cubo 2 cm en vez de levantarlo
    before = [Cube("azul", 18.8, 4.9, 0)]
    after = [Cube("azul", 17.4, 3.5, 0)]
    assert not grab_succeeded(before, after, before[0])


def test_cube_still_in_place_is_not_a_success():
    before = [Cube("azul", 15, 0, 0)]
    assert not grab_succeeded(before, list(before), before[0])


def test_brick_pattern_is_solvable():
    cubes = brick()
    assert choose_grasp(cubes, G, ALWAYS) is not None or plan_push(cubes, G, ALWAYS) is not None


def test_after_push_some_cube_is_graspable():
    plan = plan_push(block_2x2(), G, ALWAYS)
    assert choose_grasp(plan.predicted, G, ALWAYS) is not None


def test_push_slides_the_whole_row_in_line():
    plan = plan_push(block_2x2(), G, ALWAYS)
    moved = [c for c, o in zip(plan.predicted, block_2x2()) if (c.x, c.y) != (o.x, o.y)]
    assert len(moved) == 2                                    # se corre una fila entera, no un cubo


def test_push_uses_point_ok_for_pusher_positions():
    # el filtro de candidatos exige color; el empujador (sin color) se evalúa con point_ok
    only_colored = lambda c: c.color == "azul"  # noqa: E731
    assert plan_push(block_2x2(), G, only_colored) is None
    assert plan_push(block_2x2(), G, only_colored, point_ok=ALWAYS) is not None


def test_push_directions_include_any_angle_when_enabled():
    from dataclasses import replace
    from grasp import push_dirs
    c = Cube("azul", 15, 0, 10.0)
    assert sorted(d % 360 for d in push_dirs(c, G)) == [10.0, 100.0, 190.0, 280.0]   # solo caras
    dirs = [d % 360 for d in push_dirs(c, replace(G, push_dir_step=30.0))]
    assert 45.0 not in dirs and 30.0 in dirs and 60.0 in dirs and len(dirs) == 4 + 12


def test_any_direction_push_still_solves_2x2():
    from dataclasses import replace
    plan = plan_push(block_2x2(), replace(G, push_dir_step=30.0), ALWAYS)
    assert plan is not None and choose_grasp(plan.predicted, G, ALWAYS) is not None


def test_no_push_needed_when_something_is_graspable():
    assert plan_push(row_x(3), G, ALWAYS) is None


# --- 31-10: margen lateral, empujes perpendiculares primero, colores ---------------------------
from dataclasses import replace as _replace  # noqa: E402


def front_offset_case(color_b="azul"):
    """Cubo A con un vecino B delante y corrido medio cubo de costado (esquina del ladrillo)."""
    a = Cube("azul", 15.0, 0.0, 0)
    b = Cube(color_b, 15.0 - 1.9 - 0.6, 2.25, 0)  # delante (hacia la base), con su esquina asomando
    return a, b


def test_lateral_margin_lets_a_finger_brush_past_a_corner():
    a, b = front_offset_case()
    strict = _replace(G, error_lateral=0.5)
    loose = _replace(G, error_lateral=0.2)
    assert not axis_is_free(a, [b], 0.0, strict)
    assert axis_is_free(a, [b], 0.0, loose)


def test_push_prefers_face_normals_over_diagonals():
    plan = plan_push(block_2x2(), _replace(G, push_dir_step=30.0), ALWAYS)
    dx, dy = plan.direction
    assert abs(dx) < 1e-6 or abs(dy) < 1e-6


def test_pusher_keeps_extra_gap_from_the_cube():
    g = _replace(G, push_gap=0.4)
    plan = plan_push(block_2x2(), g, ALWAYS)
    c, (dx, dy) = plan.cube, plan.direction
    back = (c.x - plan.start[0]) * dx + (c.y - plan.start[1]) * dy
    assert back >= g.cube / 2 + g.finger_thick + g.error + 0.4 - 1e-6
    travel = ((plan.end[0] - plan.start[0]) ** 2 + (plan.end[1] - plan.start[1]) ** 2) ** 0.5
    assert travel == pytest.approx(g.push + g.error + 0.4)


def side_neighbor(color_b, gap=0.35):
    a = Cube("azul", 15.0, 0.0, 0)
    b = Cube(color_b, 15.0, 1.9 + gap, 0)          # al costado, casi pegado
    return a, b


def test_axis_blocked_when_a_different_colour_cube_could_be_pinched_too():
    a, b = side_neighbor("amarillo")
    g = _replace(G, error_lateral=0.2)
    assert not axis_is_free(a, [b], 0.0, g)        # dedos delante/detrás: abrazarían también a B


def test_same_colour_neighbour_may_be_pinched_too():
    a, b = side_neighbor("azul")
    g = _replace(G, error_lateral=0.2)
    assert axis_is_free(a, [b], 0.0, g)            # si se lleva dos azules, van a la misma caja
