"""Genera el informe preliminar y la chuleta de la defensa de Perry.

  py docs/informe/figuras.py      # primero las figuras
  py docs/informe/generar_pdf.py  # -> docs/informe/informe_preliminar_perry.pdf y chuleta_defensa_perry.pdf

Formato copiado del informe de Computación en la Nube (HydroValley): carta, márgenes de 25 mm, Times 11 pt.
Lo que falta saber va marcado en rojo como [DATO: ...] o [FUENTE: ...]: nunca se inventa.
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

HERE = Path(__file__).resolve().parent
FIG = HERE / "figuras"
DIAG = HERE.parent / "diagramas"

FONTS = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("Times", str(FONTS / "times.ttf")))
pdfmetrics.registerFont(TTFont("Times-B", str(FONTS / "timesbd.ttf")))
pdfmetrics.registerFont(TTFont("Times-I", str(FONTS / "timesi.ttf")))
pdfmetrics.registerFont(TTFont("Times-BI", str(FONTS / "timesbi.ttf")))
pdfmetrics.registerFont(TTFont("Mono", str(FONTS / "consola.ttf")))
pdfmetrics.registerFontFamily("Times", normal="Times", bold="Times-B", italic="Times-I", boldItalic="Times-BI")

BODY = ParagraphStyle("body", fontName="Times", fontSize=11, leading=14.2, alignment=TA_JUSTIFY, spaceAfter=6)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=10, leading=12.4, alignment=TA_LEFT, spaceAfter=0)
CELL = ParagraphStyle("cell", parent=SMALL, fontSize=9.6, leading=11.6)
CELLB = ParagraphStyle("cellb", parent=CELL, fontName="Times-B")
H1 = ParagraphStyle("h1", fontName="Times-B", fontSize=13, leading=16, spaceBefore=10, spaceAfter=6, keepWithNext=1)
H2 = ParagraphStyle("h2", fontName="Times-B", fontSize=11.5, leading=14, spaceBefore=7, spaceAfter=4, keepWithNext=1)
CAP = ParagraphStyle("cap", parent=SMALL, alignment=TA_CENTER, spaceBefore=3, spaceAfter=8)
CENTER = ParagraphStyle("center", parent=BODY, alignment=TA_CENTER, spaceAfter=0)
REF = ParagraphStyle("ref", parent=BODY, fontSize=10, leading=12.4, leftIndent=14, firstLineIndent=-14,
                     alignment=TA_LEFT, spaceAfter=3)
BULLET = ParagraphStyle("bullet", parent=BODY, leftIndent=14, bulletIndent=3, spaceAfter=3)
NUM = ParagraphStyle("num", parent=BODY, leftIndent=16, bulletIndent=2, spaceAfter=3)

RED = "#c0392b"


def ph(kind, text):
    """Marca un dato o fuente que falta: se ve en rojo para completarlo antes de entregar."""
    return f'<font color="{RED}">[{kind}: {text}]</font>'


def p(text, style=BODY):
    return Paragraph(text, style)


def bullets(items, style=BULLET, numbered=False):
    return [Paragraph(t, style, bulletText=(f"{i}." if numbered else "•")) for i, t in enumerate(items, 1)]


class Numbering:
    """Numeración corrida de tablas y figuras (con pie al estilo del informe de la nube)."""

    def __init__(self):
        self.t = self.f = 0

    def table(self, title, rows, widths, header=True, font=CELL):
        self.t += 1
        data = [[Paragraph(str(c), CELLB if (header and i == 0) else font) for c in r] for i, r in enumerate(rows)]
        tbl = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="CENTER")
        style = [("VALIGN", (0, 0), (-1, -1), "TOP"),
                 ("LINEABOVE", (0, 0), (-1, 0), 1.0, colors.black),
                 ("LINEBELOW", (0, -1), (-1, -1), 1.0, colors.black),
                 ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
                 ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
        if header:
            style.append(("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black))
        tbl.setStyle(TableStyle(style))
        cap = Paragraph(f"<b>Tabla {self.t}:</b> {title}", CAP)
        return KeepTogether([cap, tbl, Spacer(1, 8)])

    def figure(self, path, title, width):
        self.f += 1
        from reportlab.lib.utils import ImageReader
        iw, ih = ImageReader(str(path)).getSize()
        img = Image(str(path), width=width, height=width * ih / iw)
        return KeepTogether([img, Paragraph(f"<b>Figura {self.f}:</b> {title}", CAP)])


def page_number(canvas, doc):
    if doc.page > 1:
        canvas.setFont("Times", 10)
        canvas.drawCentredString(letter[0] / 2, 14 * mm, str(doc.page))


def cover(title, subtitle):
    head = ["Universidad Católica Andrés Bello – Extensión Guayana", "Facultad de Ingeniería",
            "Escuela de Ingeniería Informática", "Cátedra: " + ph("DATO", "nombre exacto de la cátedra de Robótica"),
            "Puerto Ordaz – Estado Bolívar"]
    out = [Image(str(FIG / "logo_ucab.png"), width=110 * mm, height=110 * mm * 280 / 1760), Spacer(1, 16 * mm)]
    out += [p(h, CENTER) for h in head] + [Spacer(1, 30 * mm)]
    out += [p(f"<b>{title}</b>", ParagraphStyle("t", parent=CENTER, fontSize=16, leading=20)), Spacer(1, 4 * mm),
            p(subtitle, ParagraphStyle("st", parent=CENTER, fontSize=11.5, textColor=colors.HexColor("#555555"))),
            Spacer(1, 32 * mm)]
    left = ParagraphStyle("l", parent=SMALL, fontSize=11)
    right = ParagraphStyle("r", parent=left, alignment=TA_RIGHT)
    people = Table([[p("<b>Docente:</b>", left), p("<b>Estudiantes:</b>", right)],
                    [p(ph("DATO", "docente de la cátedra"), left),
                     p("Aliendres, Ignacio<br/>Baczek, Cristian<br/>" + ph("DATO", "resto del equipo de Perry"), right)]],
                   colWidths=[80 * mm, 86 * mm])
    people.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    out += [people, Spacer(1, 22 * mm), p("Ciudad Guayana, noviembre de 2026", CENTER), PageBreak()]
    return out


# ------------------------------------------------------------------------------------------------ informe
def informe():
    n = Numbering()
    W = 166 * mm
    s = cover("Perry: brazo robótico de cinco grados de libertad que clasifica cubos por color con visión por "
              "computador dentro de un sistema multirobot", "Informe preliminar")

    s += [p("1. Introducción", H1),
          p("Los brazos robóticos resuelven tareas repetitivas, como tomar piezas y clasificarlas, con una precisión "
            "que no se agota con el uso continuo " + ph("FUENTE", "cifra de robots industriales instalados, IFR World "
            "Robotics") + ". Cuando las piezas no llegan siempre al mismo lugar, el brazo necesita ver dónde están: la "
            "visión por computador permite ubicarlas y decidir cómo tomarlas (Lugo, 2023)."),
          p("En este trabajo se desarrolló Perry, el brazo de un sistema de tres robots. Dos robots móviles, Phineas y "
            "Ferb, recogen cubos de la pista y los dejan en una zona azul frente al brazo; Perry los ve con una cámara "
            "cenital, los toma y los lleva a su caja según el color. El brazo es el mismo modelo antropomórfico de "
            "cinco grados de libertad que usaron Saad (2015) y Lugo (2023) en la UCAB Guayana."),
          p("El informe se organiza en siete secciones. En la sección 2 se plantean el problema y los objetivos; la "
            "sección 3 analiza el punto de partida, las alternativas y los requerimientos; la sección 4 presenta el "
            "diseño; la sección 5, la implementación y la calibración; la sección 6 reporta las pruebas con sus cifras, "
            "y la sección 7 recoge las conclusiones. El código, los registros de cada corrida y las pruebas "
            "automatizadas están en el repositorio del proyecto (Aliendres et al., 2026)."),

          p("2. El problema y la propuesta", H1),
          p("2.1. Planteamiento del problema", H2),
          p("Lugo (2023) desarrolló un sistema de clasificación con este mismo brazo y la misma cámara (Microsoft "
            "LifeCam Studio). Reconocía piezas de jenga de 1,5 × 2,5 × 7,5 cm sobre un área de trabajo de 70 × 70 cm y "
            "las llevaba a una caja con un error promedio de 0,12 cm en X y 0,11 cm en Y (Lugo, 2023, p. 53). En el "
            "sistema multirobot cambian cuatro condiciones (ver Tabla 1)."),
          n.table("Lo que cambia respecto del sistema de Lugo (2023)", [
              ["Condición nueva", "Problema que plantea"],
              ["Los cubos los dejan robots, no una persona", "Posición y giro impredecibles; pueden llegar pegados"],
              ["Los cubos azules llegan sobre una zona azul", "Separar el cubo del fondo con la cámara"],
              ["La zona la comparten tres robots", "Nadie puede estar en ella al mismo tiempo que otro"],
              ["Servos con juego y desgaste", "La calibración de Lugo no sirve tal cual: hay que medir la propia"]],
              [72 * mm, 94 * mm]),
          p("Es por esto que se planteó un sistema que, además de clasificar, decide cómo tomar cada cubo según los que "
            "tiene alrededor, verifica cada agarre y coordina el uso de la zona con los otros dos robots."),
          p("2.2. Objetivos", H2),
          p("<b>Objetivo general.</b> Desarrollar un sistema de visión y control para que un brazo robótico de cinco "
            "grados de libertad clasifique por color los cubos que entregan dos robots móviles."),
          p("<b>Objetivos específicos.</b>", BODY)]
    s += bullets(["Analizar el brazo, su cinemática y el sistema de Lugo (2023) frente a las condiciones del sistema "
                  "multirobot.",
                  "Definir los requerimientos funcionales y no funcionales con base en el análisis realizado.",
                  "Diseñar la visión, el planificador de agarre y la coordinación de la zona según los requerimientos "
                  "definidos.",
                  "Construir y calibrar el software del brazo con base en el diseño elaborado.",
                  "Validar el sistema mediante pruebas de precisión, corridas de clasificación y pruebas automatizadas."],
                 NUM, numbered=True)
    s += [p("2.3. Alcance y limitaciones", H2),
          p("Se contemplaron cubos azules y amarillos de 1,9 cm, dejados dentro de una franja de entrega entre 12 y "
            "19,5 cm del eje del brazo, tomados siempre con la pinza vertical. El sistema se opera desde un panel web y "
            "corre en una Raspberry Pi 4. Del lado de Perry se implementó la coordinación de la zona según el contrato "
            "de los robots móviles. No se contemplaron el modelo dinámico del brazo, los cubos apilados ni otros "
            "colores: el rojo, por regla de la pista, se ignora. La prueba integrada con Phineas y Ferb quedó "
            "pendiente " + ph("DATO", "fecha y resultado si se llega a hacer") + "."),
          p("Las limitaciones fueron tres. Primero, los servos no informan su posición y la base tiene unos 7° de juego; "
            "se mitigó llegando siempre a la base desde el mismo lado y midiendo la precisión con una prueba propia. "
            "Segundo, la cámara cenital no tiene un soporte fijo y se movió dos veces; se mitigó calibrándola con las "
            "esquinas de la zona azul, de modo que recalibrar es volver a marcar cuatro puntos. Tercero, la Pi no tiene "
            "internet en el laboratorio; la imagen de Docker se construye en una PC y se pasa por cable."),

          p("3. Análisis", H1),
          p("3.1. Punto de partida", H2),
          p("La cinemática inversa obtiene los ángulos de las articulaciones a partir de la posición que se quiere para "
            "el extremo del brazo (Barrientos et al., 2007). Lugo (2023, pp. 38–40) la resolvió con geometría: con la "
            "pinza perpendicular a la mesa, el brazo forma un triángulo rectángulo y uno obtuso; la ley del coseno da "
            "el codo y las sumas de ángulos dan el hombro y la muñeca. La base sale de θ₁ = atan(y/x). Para enviar los "
            "ángulos a la tarjeta Pololu Maestro, que solo recibe pulsos (Pololu Corporation, s. f.), los convirtió con "
            "una recta entre dos puntos conocidos de cada servo. Perry reutilizó ese modelo y esa conversión, con las "
            "medidas de su propio brazo (ver Figura 2)."),
          p("3.2. Alternativas evaluadas", H2),
          p("Teniendo el problema delimitado, se compararon alternativas en cinco decisiones (ver Tabla 2). La de más "
            "peso fue la primera: los ángulos de Lugo son exactos, pero la conversión a pulsos medida con fotos tenía "
            "errores de unos 3°, que con el brazo estirado mueven la punta cerca de 1 cm."),
          n.table("Decisiones de diseño", [
              ["Decisión", "Alternativas", "Elegida y por qué"],
              ["Cómo llegar al cubo", "Cinemática de Lugo con ángulos convertidos a pulsos; tabla enseñada",
               "Tabla enseñada: pulsos medidos con la pinza agarrando de verdad a cada distancia. Absorbe la "
               "calibración y el resorte del hombro. La cinemática se conservó para la base y como referencia"],
              ["Encontrar los cubos", "Sustracción de fondo; color en HSV",
               "HSV con un rango que excluye el azul de la zona (fondo H 103–104; cubos H 113–124). Más simple; la "
               "sustracción queda si cambia la luz"],
              ["Cubos pegados del mismo color", "Separar por forma; por área y k-means",
               "Área y k-means (Lloyd, 1982): la cantidad sale del área; funciona con filas, en L y con giros distintos"],
              ["Cubo sin espacio para los dedos", "Arrastrarlo apoyando la pinza; empujarlo con la pinza cerrada",
               "Empujar: arrastrar patinaba y forzaba el hombro"],
              ["Comunicación con los carros", "MQTT; HTTP; ROS 2",
               "ROS 2: es el contrato que ya programaron los carros. En la Pi (Debian 13) corre en Docker"]],
              [36 * mm, 50 * mm, 80 * mm]),
          p("3.3. Requerimientos", H2),
          p("Con base en el análisis se definieron los requerimientos de la Tabla 3. Cada no funcional lleva una cifra "
            "para poder verificarlo en las pruebas."),
          n.table("Requerimientos principales", [
              ["ID", "Requerimiento"],
              ["RF-01", "El sistema debe detectar los cubos azules y amarillos de la zona y calcular su posición en cm "
                        "y su giro."],
              ["RF-02", "El sistema debe llevar cada cubo a su caja: azul a la amarilla y amarillo a la verde."],
              ["RF-03", "El sistema debe ignorar y avisar los cubos que están fuera de su alcance."],
              ["RF-04", "El sistema debe separar empujando los cubos que no dejan espacio para los dedos."],
              ["RF-05", "El sistema debe detectar un agarre fallido y reintentarlo una vez."],
              ["RF-06", "El operador debe poder iniciar, ir paso a paso, solo mirar, cancelar y elegir un color desde "
                        "un panel web."],
              ["RF-07", "El sistema debe registrar cada ciclo (fotos, decisión y resultado) para poder repetirlo."],
              ["RF-08", "El sistema debe coordinar la zona con los carros: llave, espera y cierre."],
              ["RNF-01", "El error medio de posicionamiento debe ser menor o igual a 5 mm."],
              ["RNF-02", "Tras una entrega, el brazo no debe moverse antes de 2 s ni con la zona ocupada o en "
                         "movimiento."],
              ["RNF-03", "El sistema debe funcionar en una Raspberry Pi 4 sin internet."],
              ["RNF-04", "Toda medida y todo pulso deben estar en un único archivo de configuración."],
              ["RES-01", "Python; tarjeta Pololu Mini Maestro 12; cámara cenital de 640 × 480 a 70 cm."],
              ["RES-02", "ROS 2 Lyrical con los mensajes de multirobot_interfaces (Vielma, 2026)."]],
              [17 * mm, 149 * mm]),

          p("4. Diseño de la solución", H1),
          p("4.1. Coordenadas y ángulos", H2),
          p("Teniendo los requerimientos definidos, se fijó un único sistema de coordenadas: el origen está en la mesa, "
            "bajo el eje de giro de la base; X apunta al centro de la zona, Y a la izquierda y Z hacia arriba (ver "
            "Figura 1). La franja verde es la parte de la zona que el brazo alcanza: entre 11,9 y 19,5 cm del eje. La "
            "franja del fondo de la zona azul queda fuera de alcance."),
          n.figure(FIG / "zona_arriba.png", "Zona de entrega, alcance del brazo y cajas, vistos desde arriba (cm). "
                   "Esquinas de la zona tomadas de la calibración de la cámara.", 104 * mm),
          p("Los ángulos siguen las convenciones de la calibración (ver Figura 2): la base mide 0° sobre el eje X y es "
            "positiva hacia la izquierda; el hombro se mide desde la horizontal (90° es vertical); el codo y la muñeca "
            "son ángulos interiores (180° es recto), y el giro de la pinza es 0° cuando los dedos cierran de izquierda "
            "a derecha. Las medidas del brazo son E1 = 3,3 cm (mesa a hombro), E2 = 10 cm, E3 = 12 cm y "
            "E45 = 10,13 cm (muñeca a la punta de la pinza)."),
          n.figure(FIG / "brazo_perfil.png", "Postura calculada con la cinemática de Lugo (2023) y las medidas de "
                   "Perry para tomar un cubo a 16 cm.", 120 * mm),
          p("4.2. Arquitectura del ciclo", H2),
          p("Cada cubo recorre cinco etapas (ver Figura 3). La cámara saca la foto recién cuando la escena está quieta, "
            "para que el brazo no aparezca saliendo de la imagen. La visión convierte píxeles en centímetros con una "
            "homografía calculada con las cuatro esquinas de la zona (Hartley y Zisserman, 2004), detecta los cubos por "
            "color, separa los pegados y corrige la paralaje: a 70 cm, la cámara ve la cara de arriba del cubo corrida "
            "hacia afuera en la proporción 1,9 / 70. El planificador decide si agarrar, empujar o terminar. El brazo "
            "llega por arriba, siempre a la base desde el mismo lado, y baja el hombro despacio. La verificación cuenta "
            "los cubos: el agarre salió si hay uno menos de ese color."),
          n.figure(FIG / "ciclo.png", "Recorrido de un cubo, de la cámara a la caja.", W),
          p("4.3. Planificador de agarre", H2),
          p("Un cubo se puede tomar cerrando la pinza en dos direcciones: según su giro o 90° más. Para cada una se "
            "dibujan las huellas de los dos dedos (0,5 × 1,9 cm, más 0,5 cm de error a lo largo del cierre). El eje está "
            "libre si ninguna huella pisa otro cubo y si entre los dedos no puede quedar un cubo de otro color. Entre "
            "los ejes libres se elige el que menos gira la pinza y el más cercano al brazo. Si ningún cubo tiene un eje "
            "libre, se planifica un empuje de 3,8 cm, probando direcciones cada 30°, y se exige que todo cubo movido "
            "quede a 1 cm o más de los dos bordes del alcance. Tras tres empujes seguidos sin poder agarrar, la zona se "
            "declara bloqueada."),
          p("4.4. Coordinación de la zona", H2),
          p("La zona se reparte con una sola llave para los tres robots. El árbitro corre en la Pi de Perry: un carro "
            "pide la llave (/zone/request), entra, deja el cubo y la devuelve (/zone/release); el árbitro publica dos "
            "veces por segundo quién la tiene (/zone/occupant), y si esa señal se corta 2 s, los carros se frenan. "
            "Perry pide la misma llave antes de mover el brazo. Que un carro devuelva la llave no prueba que se fue: "
            "antes de bajar el brazo, Perry espera 2 s, una escena quieta y ningún objeto más grande que 20 cm² en la "
            "zona; si en 10 s no se cumple, la cierra (ver Figura 4). La zona también se cierra con dos cubos esperando, "
            "la llave se da por orden de llegada y Perry la cede después de un cubo si un carro espera."),
          n.figure(DIAG / "perry_zona_estados.png", "Estados de Perry frente a la zona de entrega.", 140 * mm),

          p("5. Implementación", H1),
          p("5.1. Tecnologías", H2),
          p("Habiendo definido el diseño, se construyó todo en Python; las bibliotecas pesadas de imagen están escritas "
            "en C++ por dentro. La Tabla 4 muestra las versiones usadas."),
          n.table("Tecnologías y versiones", [
              ["Elemento", "Versión", "Uso"],
              ["Python", "3.13.5 (PC y Pi)", "Todo el software"],
              ["OpenCV / NumPy", "4.11.0 / 2.2.6 (PC); 4.10.0 / 2.2.4 (Pi)", "Visión y geometría"],
              ["pyserial / PyYAML", "3.5 / 6.0.3 (PC); 6.0.2 (Pi)", "Maestro y configuración"],
              ["pytest", "9.2.0", "Pruebas automatizadas"],
              ["ROS 2 Lyrical", "imagen ros:lyrical-ros-base", "Árbitro y mensajes de la flota, en Docker"],
              ["Raspberry Pi 4", "4 GB, Debian 13 (trixie)", "Computador de Perry"],
              ["Pololu Mini Maestro 12", "—", "Pulsos a los seis servos"],
              ["Microsoft LifeCam Studio", "640 × 480", "Cámara cenital a 70 cm"]],
              [44 * mm, 62 * mm, 60 * mm]),
          p("5.2. Calibración", H2),
          p("La base se calibró por tramos con cinco puntos tocados con la pinza (de −36,6° a 36,6°) y se corrigió con la "
            "prueba de precisión. Para absorber su juego, siempre se llega a su pulso desde 100 µs más abajo. El giro "
            "de la pinza vale 0° en 1447 µs, a unos 10 µs/°. Hombro, codo y muñeca se mueven con una tabla enseñada "
            "de siete filas, entre 11,9 y 21,2 cm, que se interpola según la distancia del cubo; al agarrar, el hombro "
            "baja 30 µs más por el resorte. La pinza abre en 750 µs, cierra en 1700 µs y empuja cerrada del todo en "
            "2350 µs. Todos estos valores están en un único archivo, arm.yaml."),
          p("5.3. Panel, registro y repetición", H2),
          p("El panel web muestra la cámara en vivo y la decisión dibujada, y tiene los botones Iniciar, Paso a paso "
            "(aprobar cada movimiento), Solo mirar, Prueba de precisión, Cancelar y un selector de color. Cada corrida "
            "guarda sus fotos, un registro con hora y un archivo con cada decisión; con él, una corrida se repite con "
            "el planificador actual, y una falla entendida en la mesa se convierte en una prueba automatizada."),
          p("5.4. Raspberry Pi y Docker", H2),
          p("El software se llevó a la Pi por SSH sobre un cable directo. Se encontró que la Pi no arranca si la "
            "Maestro y la cámara están conectadas al encender, por lo que se conectan después. Para la flota, el panel "
            "corre en un contenedor con ROS 2 Lyrical, con red del anfitrión; la imagen se construye en una PC "
            "emulando el procesador de la Pi y se carga por cable " + ph("DATO", "verificar en el laboratorio") + "."),

          p("6. Pruebas", H1),
          p("6.1. Precisión", H2),
          p("Una vez calibrado el brazo, se midió su precisión con un método propio, porque dejar un cubo y volver a "
            "tomarlo en el mismo punto cancela el error. El brazo baja la pinza abierta sobre el cubo, cierra sin "
            "levantar y abre: los dedos centran el cubo donde la pinza realmente bajó, y la cámara mide cuánto se "
            "corrió. Se repite girando la pinza 90° para obtener X e Y, en cinco puntos (ver Tabla 5)."),
          n.table("Prueba de precisión (31-10-2026, cinco puntos)", [
              ["Momento", "Error medio", "Observación"],
              ["Antes de recalibrar la base", "6,4 mm", "La base se quedaba corta hasta 2,9° hacia la izquierda"],
              ["Después de recalibrar la base", "3,0 mm", "Peor punto: 4,2 mm"],
              ["Tras un golpe contra una caja", "7,9 mm (3,7 sin un punto)", "Un cubo giró al cerrar (15,9 mm): "
               "desde entonces se descarta la medición si el cubo gira más de 15°"],
              ["Lugo (2023)", "1,2 mm en X; 1,1 mm en Y", "Otro método: objeto dejado sobre hoja milimetrada"]],
              [46 * mm, 38 * mm, 82 * mm]),
          p("El error de 3,0 mm cumple RNF-01. Es mayor que el de Lugo (2023), y la diferencia se explica en parte por el "
            "método: el suyo mide dónde queda el objeto; el de Perry, dónde baja la pinza, medido con una cámara cuya "
            "propia calibración tiene unos 3 mm de precisión. Con los dos métodos en el mismo brazo se podría separar "
            "cuánto aporta cada uno."),
          p("6.2. Corridas de clasificación", H2),
          p("Con la precisión verificada, se hicieron corridas completas con cubos reales, en la PC y en la Raspberry "
            "Pi (ver Tabla 6)."),
          n.table("Corridas de clasificación", [
              ["Corrida", "Resultado"],
              ["PC, 31-10", "4 de 4 cubos al primer intento; 2 ignorados por estar fuera de alcance (19,5 y 20,5 cm)."],
              ["Raspberry Pi, 31-10", "5 cubos clasificados; 1 agarre fallido, recuperado al ciclo siguiente; 1 cubo "
                                      "empujado fuera de alcance (11,7 cm), corregido con el margen de 1 cm en ambos "
                                      "bordes."],
              ["Tiempo por cubo", "Entre 22 y 34 s, mediana 27 s (18 agarres del 30 y 31-10); igual en la PC y en la "
                                  "Pi."],
              ["Carga de la Pi", "Sin caídas de tensión en 10 min; 46 °C, carga 1,2 de 4 núcleos y 344 MB de "
                                 "memoria como máximo."]],
              [36 * mm, 130 * mm]),
          p("6.3. Pruebas automatizadas", H2),
          p("Se escribieron 138 pruebas con pytest, que corren en la PC y en la Pi. Incluyen escenas reales guardadas de "
            "corridas que fallaron, que desde entonces no pueden volver a fallar sin que se note. El detector de objetos "
            "grandes se probó con fotos reales de la cámara cenital (ver Tabla 7)."),
          n.table("Detector de objeto grande con fotos reales (umbral: 20 cm²)", [
              ["Foto", "Mancha mayor", "Resultado"],
              ["Zona vacía, brazo estacionado", "0,3 cm²", "Zona despejada"],
              ["Un cubo amarillo / un cubo azul", "5,3 / 4,1 cm²", "Zona despejada"],
              ["Brazo sobre la zona", "61 cm²", "Objeto grande: no se mueve el brazo"]],
              [62 * mm, 40 * mm, 64 * mm]),
          p("6.4. Incidencias", H2),
          p("Cada falla vista en la mesa se registró con su causa y su solución (ver Tabla 8)."),
          n.table("Incidencias y soluciones", [
              ["Incidencia", "Solución"],
              ["La pinza tomaba los cubos por los vértices", "Se corrigió el signo del giro de la pinza"],
              ["Al empujar, la pinza caía sobre el cubo", "Empujar con la pinza cerrada del todo (2350 µs)"],
              ["La pose de espera izquierda golpeaba la caja amarilla", "Se desactivó; el brazo espera a la derecha"],
              ["La foto salía con el brazo cruzando la zona", "Esperar dos cuadros seguidos casi iguales"],
              ["El fondo azul se detectaba como cubo", "El rango azul empieza en H 109"],
              ["Un empuje dejó un cubo fuera de alcance", "Margen de 1 cm en los dos bordes, con prueba"],
              ["La Pi no arrancaba", "Conectar la Maestro y la cámara después de encenderla"]],
              [80 * mm, 86 * mm]),

          p("7. Conclusiones", H1),
          p("Una vez construido el sistema y ejecutadas las pruebas, se concluye que:")]
    s += bullets([
        "El modelo geométrico de Lugo (2023) siguió siendo válido para este brazo, pero no su conversión a pulsos: "
        "medir los pulsos con la pinza agarrando de verdad resultó más preciso que convertir ángulos exactos con una "
        "calibración aproximada.",
        "Recalibrar la base con la prueba de precisión bajó el error medio de 6,4 a 3,0 mm, por debajo del umbral de "
        "5 mm. Medir antes de ajustar evitó corregir lo que no estaba mal: tras el golpe, el error alto venía de una "
        "medición defectuosa y no del brazo.",
        "Planificar cada agarre según los cubos vecinos permitió tomar cubos pegados y girados, y empujar solo cuando "
        "no había otra salida. En la Pi se clasificaron cinco cubos con un solo agarre fallido, recuperado.",
        "Calibrar la cámara con las esquinas de la zona, en lugar de una hoja que se retira, convirtió la "
        "recalibración en marcar cuatro puntos.",
        "Guardar cada corrida y convertir sus fallas en pruebas automatizadas permitió corregir sin romper lo que ya "
        "funcionaba: 138 pruebas protegen el sistema.",
        "Usar la misma llave para carros y brazo, y no confiar solo en ella antes de mover el brazo, protegió el caso "
        "más peligroso: un carro detenido dentro de la zona.",
        "La Raspberry Pi 4 no fue el cuello de botella: el tiempo por cubo fue el mismo que en la PC, y lo marca la "
        "mecánica del brazo."], NUM, numbered=True)
    s += [p("Con base en estas conclusiones se recomienda: aplicar el método de medición de Lugo (2023) en este brazo "
            "para comparar ambos con la misma referencia; fijar la cámara con un soporte rígido; medir el umbral de "
            "objeto grande con la pala real de cada carro; reemplazar los servos con más juego, y completar la prueba "
            "integrada con Phineas y Ferb."),

          p("Referencias bibliográficas", H1)]
    refs = [
        "Aliendres, I., Baczek, C. y " + ph("DATO", "resto del equipo") + " (2026). <i>Robot_Claw</i> [Repositorio de "
        "código fuente]. GitHub. https://github.com/Kobalt09/Robot_Claw",
        "Barrientos, A., Peñín, L. F., Balaguer, C. y Aracil, R. (2007). <i>Fundamentos de robótica</i> (2.ª ed.). "
        "McGraw-Hill.",
        "Hartley, R. y Zisserman, A. (2004). <i>Multiple view geometry in computer vision</i> (2.ª ed.). Cambridge "
        "University Press.",
        "Lloyd, S. (1982). Least squares quantization in PCM. <i>IEEE Transactions on Information Theory, 28</i>(2), "
        "129–137.",
        "Lugo, M. (2023). <i>Sistema de clasificación basado en visión por computador con brazo robótico antropomórfico "
        "de 5 grados de libertad</i> [Trabajo de grado]. Universidad Católica Andrés Bello.",
        "Pololu Corporation. (s. f.). <i>Maestro servo controller user's guide</i>. https://www.pololu.com/docs/0J40",
        "Saad, J. (2015). <i>Entorno de programación para simular y controlar un brazo robótico antropomórfico de 5 "
        "grados de libertad</i> [Trabajo de grado]. Universidad Católica Andrés Bello.",
        "Vielma, A. (2026). <i>ucab-multirobot</i> [Repositorio de código fuente]. GitHub. "
        "https://github.com/alejandrovielma/ucab-multirobot"]
    s += [p(r, REF) for r in refs]
    return s


# ------------------------------------------------------------------------------------------------ chuleta
def chuleta():
    n = Numbering()
    Q = ParagraphStyle("q", parent=BODY, fontName="Times-B", spaceBefore=5, spaceAfter=1, alignment=TA_LEFT)
    A = ParagraphStyle("a", parent=BODY, spaceAfter=3)
    s = [p("<b>Perry: chuleta para la defensa</b>", ParagraphStyle("tt", parent=CENTER, fontSize=17, leading=21)),
         p("Lo esencial, sin palabras complicadas. Cada número sale del repositorio (arm.yaml y logs).",
           ParagraphStyle("st", parent=CENTER, fontSize=10.5, textColor=colors.HexColor("#555555"))),
         Spacer(1, 6),

         p("1. Perry en treinta segundos", H1),
         p("«Perry es el brazo del sistema. Phineas y Ferb dejan cubos en la zona azul; una cámara a 70 cm los ve, Perry "
           "calcula dónde están en centímetros, decide cómo tomar cada uno sin chocar con los demás, lo lleva a su caja "
           "y comprueba con la cámara que salió bien. Partimos de la tesis de Miguel Lugo, que usó este mismo brazo, y "
           "le agregamos lo que el sistema de tres robots exige: cubos pegados, fondo azul y turnos para usar la "
           "zona.»"),

         p("2. Números que hay que saber", H1),
         n.table("Números clave", [
             ["Qué", "Valor"],
             ["Brazo", "5 grados de libertad + pinza; 6 servos en una Pololu Mini Maestro 12"],
             ["Eslabones", "E1 = 3,3 · E2 = 10 · E3 = 12 · E45 = 10,13 cm"],
             ["Alcance", "de 11,9 a 19,5 cm del eje de la base, con la pinza vertical"],
             ["Cubo", "1,9 cm; azul va a la caja amarilla (izquierda), amarillo a la verde (derecha)"],
             ["Cámara", "640 × 480 a 70 cm; misma LifeCam Studio que Lugo"],
             ["Precisión", "3,0 mm de error medio (Lugo: 1,2 / 1,1 mm, con otro método); umbral 5 mm"],
             ["Tiempo por cubo", "27 s de mediana (22 a 34 s)"],
             ["Pruebas", "138 automatizadas; corrida en la Pi: 5 cubos, 1 fallo recuperado"]],
             [34 * mm, 132 * mm]),

         p("3. Los ángulos", H1),
         n.figure(FIG / "brazo_perfil.png", "Postura real calculada para un cubo a 16 cm.", 112 * mm)]
    s += bullets([
        "<b>Base:</b> gira todo el brazo. 0° mira al centro de la zona; positivo, a la izquierda. Sale de "
        "θ₁ = atan2(y, x): es la ecuación 34 de Lugo.",
        "<b>Hombro:</b> se mide desde la horizontal; 90° es el brazo vertical.",
        "<b>Codo y muñeca:</b> ángulos interiores; 180° es recto.",
        "<b>Cómo salen (Lugo):</b> con la pinza vertical, el brazo forma un triángulo rectángulo y uno obtuso. La ley "
        "del coseno da el codo; sumando ángulos de los dos triángulos salen el hombro y la muñeca.",
        "<b>Lo que cambiamos:</b> los ángulos de Lugo son exactos, pero convertirlos a pulsos tenía unos 3° de error "
        "(cerca de 1 cm en la punta). Por eso hombro, codo y muñeca usan una <b>tabla enseñada</b>: pulsos medidos con "
        "la pinza agarrando de verdad a 7 distancias, e interpolados entre ellas.",
        "<b>Giro de la pinza:</b> se alinea con el cubo; 0° = dedos cerrando de izquierda a derecha."])
    s += [p("4. La zona y el alcance", H1),
          n.figure(FIG / "zona_arriba.png", "Coordenadas, franja de entrega y cajas.", 108 * mm)]
    s += bullets([
        "<b>Origen:</b> en la mesa, bajo el eje de la base. X hacia la zona, Y a la izquierda.",
        "<b>Por qué 19,5 cm:</b> más lejos, el hombro no aguanta el brazo estirado. El fondo de la zona azul "
        "(hasta 21,5 cm) no se alcanza: por eso se pidió a los carros dejar los cubos en la franja verde.",
        "<b>Base desde abajo:</b> tiene unos 7° de juego; siempre se llega a su pulso desde el mismo lado."])
    s += [p("5. Cómo ve y cómo decide", H1),
          p("Cada cubo pasa por cinco pasos, y se repite hasta que no quedan cubos que se puedan tomar (ver Figura 3)."),
          n.figure(FIG / "ciclo.png", "El ciclo de un cubo.", 166 * mm)]
    s += bullets([
        "<b>Píxeles a centímetros:</b> una homografía hecha con las 4 esquinas de la zona azul. Si mueven la cámara, "
        "se vuelven a marcar esas 4 esquinas.",
        "<b>Cubo azul sobre fondo azul:</b> son azules distintos. El fondo tiene tono H 103–104 y los cubos 113–124; "
        "el rango de los cubos empieza en 109.",
        "<b>Cubos pegados:</b> se cuentan por el área de la mancha y se separan con k-means.",
        "<b>Paralaje:</b> la cámara ve la cara de arriba del cubo corrida hacia afuera; se corrige con la altura "
        "(70 cm) y el lado del cubo (1,9 cm).",
        "<b>Decidir:</b> cada cubo tiene dos formas de cerrar la pinza. Se elige una donde los dedos no pisen otro cubo "
        "y no quede uno de otro color entre ellos. Si no hay ninguna, empuja 3,8 cm para separar.",
        "<b>Verificar:</b> después de soltar, cuenta los cubos. Si sigue igual, el agarre falló: reintenta una vez."])
    s += [p("6. Coordinación con los carros", H1)]
    s += bullets([
        "<b>Una sola llave</b> para los tres robots. El árbitro corre en la Pi de Perry. Quien tiene la llave entra; "
        "los demás esperan afuera.",
        "<b>Latido:</b> el árbitro avisa dos veces por segundo quién tiene la llave. Si Perry se cae, la señal se corta "
        "y los carros se frenan solos a los 2 s.",
        "<b>Asentando:</b> que un carro devuelva la llave no prueba que se fue. Perry espera 2 s, la escena quieta y "
        "ninguna mancha de más de 20 cm² (un cubo mide unos 4; el brazo, 61). Si en 10 s no se despeja, cierra la zona.",
        "<b>«No traigan más»:</b> con 2 cubos esperando, la zona bloqueada o Stop desde el panel.",
        "<b>Turnos:</b> la llave va al primero que la pidió; Perry la cede después de un cubo si un carro espera.",
        "<b>Por qué ROS 2:</b> es el contrato que ya programaron los carros. La Pi de Perry usa Debian, que no tiene "
        "ROS: por eso corre en Docker."])
    s += [p("7. Preguntas difíciles", H1)]
    qa = [
        ("¿Por qué no usaron la cinemática inversa de Lugo?",
         "Sí la usamos: la base sale de su ecuación, y su modelo da los ángulos. Lo que no servía era pasar esos "
         "ángulos a pulsos con una calibración medida con fotos (unos 3° de error). La tabla enseñada mide el pulso "
         "donde la pinza agarra de verdad."),
        ("¿Por qué su error (3,0 mm) es mayor que el de Lugo (1,2 mm)?",
         "Medimos otra cosa. Lugo midió dónde quedó el objeto sobre papel milimetrado; nosotros, dónde baja la pinza, "
         "con la cámara, que tiene sus propios 3 mm de calibración. Además, los servos tienen juego. Igual cumple el "
         "umbral de 5 mm, y la prueba ya detectó y corrigió una base descalibrada (de 6,4 a 3,0 mm)."),
        ("¿Qué pasa si se mueve la cámara?",
         "Se vuelven a marcar las 4 esquinas de la zona azul en el panel. Los centímetros de esas esquinas no cambian."),
        ("¿Y si el agarre falla?",
         "La cámara lo detecta al contar los cubos; reintenta una vez y después ignora ese cubo. Con dos fallas "
         "seguidas se detiene, porque puede haber un desajuste."),
        ("¿Qué hace si los cubos están pegados?",
         "Busca un cubo con espacio para los dedos. Si ninguno lo tiene, empuja uno para separarlos, cuidando que "
         "ninguno quede fuera de alcance. Tras tres empujes sin éxito, cierra la zona."),
        ("¿Qué pasa si un carro se queda en la zona?",
         "Perry no baja el brazo: la mancha del carro es mucho más grande que un cubo. A los 10 s cierra la zona y "
         "avisa en el panel."),
        ("¿Funciona sin los carros?",
         "Sí. Desde el panel: Iniciar, Paso a paso, Solo mirar, elegir color y Prueba de precisión. Lo que no se ve "
         "sin carros es el arranque automático tras una entrega."),
        ("¿Por qué Python?",
         "Las decisiones son pocas por segundo; lo pesado es la imagen, y OpenCV y NumPy están en C++ por dentro."),
        ("¿Cómo saben que un cambio no rompió nada?",
         "138 pruebas automatizadas, incluidas escenas reales que fallaron alguna vez. Cada corrida queda grabada y "
         "se puede repetir con el código nuevo.")]
    for q, a in qa:
        s.append(KeepTogether([p(q, Q), p(a, A)]))
    return s


def build(name, story, title):
    out = HERE / name
    doc = SimpleDocTemplate(str(out), pagesize=letter, leftMargin=25 * mm, rightMargin=25 * mm,
                            topMargin=22 * mm, bottomMargin=22 * mm, title=title, author="Equipo Perry",
                            subject="Robot_Claw, UCAB Guayana")
    doc.build(story, onFirstPage=page_number, onLaterPages=page_number)
    print(out)


if __name__ == "__main__":
    build("informe_preliminar_perry.pdf", informe(), "Perry: informe preliminar")
    build("chuleta_defensa_perry.pdf", chuleta(), "Perry: chuleta para la defensa")
