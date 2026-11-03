"""Figuras del informe y de la chuleta de Perry, calculadas con los datos reales del repo.

  py docs/informe/figuras.py

- brazo_perfil.png: la postura que da perry/kinematics.py para un cubo a 16 cm, con las medidas de arm.yaml.
- zona_arriba.png: la zona azul de la calibración (camera.corners_cm), el alcance y las cajas.
- ciclo.png: el recorrido de un cubo, de la cámara a la caja.
"""
import sys
from math import atan2, cos, degrees, hypot, radians, sin
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import yaml  # noqa: E402
from matplotlib.patches import Arc, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle, Wedge  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "perry"))
from kinematics import inverse_kinematics  # noqa: E402

CFG = yaml.safe_load((ROOT / "perry" / "config" / "arm.yaml").read_text(encoding="utf-8"))
OUT = HERE / "figuras"
OUT.mkdir(exist_ok=True)
plt.rcParams.update({"font.family": "Times New Roman", "font.size": 11, "mathtext.fontset": "stix"})
INK, SOFT, ACCENT, ZONE, BAND = "#222222", "#888888", "#c0392b", "#2f6db5", "#3c9a5f"


def brazo_perfil():
    L = CFG["links"]
    r, z = 16.0, CFG["grip_z"]
    a = inverse_kinematics(r, 0.0, z, L)
    t2, t3, t4 = a["hombro"], a["codo"], a["muneca"]
    shoulder = (0.0, L["E1"])
    elbow = (shoulder[0] + L["E2"] * cos(radians(t2)), shoulder[1] + L["E2"] * sin(radians(t2)))
    fa = t2 - (180 - t3)                          # dirección del antebrazo
    wrist = (elbow[0] + L["E3"] * cos(radians(fa)), elbow[1] + L["E3"] * sin(radians(fa)))
    tip = (wrist[0], wrist[1] - L["E45"])         # la pinza baja vertical

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.axhline(0, color=INK, lw=1.2)
    ax.add_patch(Rectangle((-1.6, 0), 3.2, 0.6, color="#bbbbbb"))
    cube = CFG["grasp"]["cube"]
    ax.add_patch(Rectangle((r - cube / 2, 0), cube, cube, color="#e2b93b", ec=INK, lw=0.6))
    pts = [(0, 0), shoulder, elbow, wrist, tip]
    ax.plot(*zip(*pts), color=INK, lw=4, solid_capstyle="round", zorder=3)
    for p in pts[1:4]:
        ax.add_patch(plt.Circle(p, 0.45, color="white", ec=INK, lw=1.5, zorder=4))

    def angle(center, a1, a2, rad, label, off):
        """Arco antihorario de a1 a a2 (grados) y su etiqueta en la bisectriz."""
        ax.add_patch(Arc(center, 2 * rad, 2 * rad, theta1=a1, theta2=a2, color=ACCENT, lw=1.4))
        m = radians((a1 + a2) / 2)
        ax.text(center[0] + (rad + off) * cos(m), center[1] + (rad + off) * sin(m), label,
                color=ACCENT, ha="center", va="center", fontsize=11)

    ax.plot([shoulder[0], shoulder[0] + 4.5], [shoulder[1]] * 2, color=SOFT, lw=0.8, ls="--")
    angle(shoulder, 0, t2, 2.6, f"hombro\n{t2:.0f}°", 1.9)                 # desde la horizontal
    angle(elbow, t2 + 180, fa + 360, 1.8, f"codo\n{t3:.0f}°", 1.7)          # interior: brazo-antebrazo
    angle(wrist, fa + 180, 270, 1.6, f"muñeca\n{t4:.0f}°", 1.9)             # interior: antebrazo-pinza

    def seg_label(p, q, text, dx=0.0, dy=0.0):
        ax.text((p[0] + q[0]) / 2 + dx, (p[1] + q[1]) / 2 + dy, text, fontsize=10, color=INK, ha="center")

    num = lambda v: f"{v:g}".replace(".", ",")  # noqa: E731
    seg_label((0, 0), shoulder, f"E1 = {num(L['E1'])}", -2.1, -0.6)
    seg_label(shoulder, elbow, f"E2 = {num(L['E2'])}", -1.7, 0.6)
    seg_label(elbow, wrist, f"E3 = {num(L['E3'])}", 0.4, 1.0)
    seg_label(wrist, tip, f"E45 = {num(L['E45'])}", 2.5, 0)
    ax.annotate("", xy=(r, -1.2), xytext=(0, -1.2), arrowprops=dict(arrowstyle="<->", color=SOFT, lw=0.9))
    ax.text(r / 2, -2.1, f"r = {num(r)} cm (distancia al eje de la base)", ha="center", fontsize=10, color=SOFT)
    ax.text(r + 1.4, cube / 2, "cubo\n1,9 cm", fontsize=9, va="center")
    ax.set_xlim(-3.5, 23)
    ax.set_ylim(-2.8, 14.5)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT / "brazo_perfil.png", dpi=200)
    plt.close(fig)


def zona_arriba():
    c = CFG["camera"]
    # en el dibujo: X (hacia la zona) hacia arriba, Y (izquierda) hacia la izquierda
    P = lambda x, y: (-y, x)  # noqa: E731
    fig, ax = plt.subplots(figsize=(6.4, 5.0))
    r_lo, r_hi = min(row["r"] for row in CFG["reach"]["rows"]), CFG["reach"]["max_r"]
    zone = [P(x, y) for x, y in c["corners_cm"]]
    ax.add_patch(Polygon(zone, closed=True, color=ZONE, alpha=0.35, lw=0))
    band = Wedge((0, 0), r_hi, 50, 130, width=r_hi - r_lo, color=BAND, alpha=0.45, lw=0)
    ax.add_patch(band)
    band.set_clip_path(Polygon(zone, closed=True, transform=ax.transData))
    ax.add_patch(Polygon(zone, closed=True, fill=False, ec=ZONE, lw=1.5))
    for rad, col, txt in ((r_lo, SOFT, f"alcance mínimo {r_lo:.1f} cm"), (r_hi, ACCENT, f"alcance máximo {r_hi:g} cm")):
        ax.add_patch(Arc((0, 0), 2 * rad, 2 * rad, theta1=35, theta2=145, color=col, lw=1.3))
    ax.text(9.8, 20.6, f"alcance máximo\n{r_hi:g} cm".replace(".", ","), color=ACCENT, fontsize=10)
    ax.text(1.5, 8.4, f"alcance mínimo\n{r_lo:.1f} cm".replace(".", ","), color=SOFT, fontsize=10, ha="left")
    ax.text(0, 16.0, "franja de entrega\n(dejar los cubos aquí)", ha="center", va="center", fontsize=10, color="white",
            fontweight="bold")
    ax.text(0, 20.6, "zona azul (fuera de alcance)", ha="center", fontsize=9, color=ZONE)
    # cajas
    for (x, y), col, name in (((10.0, 13.0), "#f1c40f", "caja amarilla\n← cubos azules"),
                              ((10.0, -13.0), "#27ae60", "caja verde\ncubos amarillos →")):
        u, v = P(x, y)
        ax.add_patch(FancyBboxPatch((u - 3, v - 3), 6, 6, boxstyle="round,pad=0.2", color=col, alpha=0.7))
        ax.text(u, v - 4.6, name, ha="center", va="top", fontsize=9)
    # ejes y base
    ax.add_patch(plt.Circle((0, 0), 1.3, color="#bbbbbb", ec=INK))
    ax.annotate("", xy=P(5.5, 0), xytext=P(0, 0), arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.3))
    ax.annotate("", xy=P(0, 5.5), xytext=P(0, 0), arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.3))
    ax.text(*P(6.2, -0.6), "X", fontsize=12)
    ax.text(*P(0.4, 6.6), "Y", fontsize=12)
    ax.text(0.5, -2.6, "eje de la base (origen)", ha="center", fontsize=9)
    # ejemplo de ángulo de base para un cubo
    cx, cy = 16.0, 5.0
    th = degrees(atan2(cy, cx))
    ax.plot([0, P(cx, cy)[0]], [0, P(cx, cy)[1]], color=INK, lw=0.8, ls="--")
    ax.add_patch(Rectangle((P(cx, cy)[0] - 0.95, P(cx, cy)[1] - 0.95), 1.9, 1.9, color="#2c3e50"))
    ax.add_patch(Arc((0, 0), 9, 9, theta1=90, theta2=90 + th, color=ACCENT, lw=1.4))
    ax.text(0.5, 3.6, f"base {th:.0f}°", color=ACCENT, fontsize=10, ha="left")
    ax.set_xlim(-18, 18)
    ax.set_ylim(-4, 23)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT / "zona_arriba.png", dpi=200)
    plt.close(fig)


def ciclo():
    steps = [("Cámara cenital", "foto a 70 cm,\ncon la escena quieta"),
             ("Visión", "homografía píxel → cm\ncolor HSV, separar pegados,\ncorregir paralaje"),
             ("Planificador", "¿agarrar, empujar\no nada?"),
             ("Brazo", "base desde abajo,\ntabla enseñada,\nbaja lento y cierra"),
             ("Caja", "suelta y verifica\ncontando cubos")]
    fig, ax = plt.subplots(figsize=(7.6, 2.1))
    w, h, gap = 1.36, 1.45, 0.26
    for i, (t, d) in enumerate(steps):
        x = i * (w + gap)
        ax.add_patch(FancyBboxPatch((x, 0), w, h, boxstyle="round,pad=0.03", fc="#f4f6f8", ec=INK, lw=0.8))
        ax.text(x + w / 2, h - 0.22, t, ha="center", va="center", fontsize=10.5, fontweight="bold")
        ax.text(x + w / 2, h / 2 - 0.16, d, ha="center", va="center", fontsize=8.3, linespacing=1.25)
        if i < len(steps) - 1:
            ax.add_patch(FancyArrowPatch((x + w + 0.02, h / 2), (x + w + gap - 0.02, h / 2),
                                         arrowstyle="-|>", mutation_scale=11, color=INK))
    total = len(steps) * (w + gap) - gap
    # vuelta por debajo de los cuadros, sin cruzarlos
    x0, x1, yb = w / 2, total - w / 2, -0.32
    ax.plot([x1, x1, x0], [-0.06, yb, yb], color=SOFT, lw=0.9)
    ax.add_patch(FancyArrowPatch((x0, yb), (x0, -0.06), arrowstyle="-|>", mutation_scale=10, color=SOFT, lw=0.9))
    ax.text(total / 2, yb - 0.2, "se repite hasta que no quedan cubos alcanzables", ha="center", fontsize=9,
            color=SOFT)
    ax.set_xlim(-0.05, total + 0.05)
    ax.set_ylim(-0.75, h + 0.05)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT / "ciclo.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    brazo_perfil()
    zona_arriba()
    ciclo()
    print("Figuras en", OUT)
