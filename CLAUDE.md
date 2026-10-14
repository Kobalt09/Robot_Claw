# Robot_Claw — Sistema Multirobot (UCAB, Robótica)

Contexto para Claude Code. Viene de una conversación previa en Claude (Cowork); este archivo resume lo decidido y lo que sigue.

## Quién y cómo trabajar

- Usuario: Ignacio, estudiante de Ingeniería Informática (UCAB Guayana). Equipo de unas doce personas; Stalin escribió la primera clase `Maestro`.
- Responde en español, simple y directo, con criterio crítico y pragmático: el objetivo es una demo que funcione.
- Código en Python. Nombres en inglés, comentarios en español. Ningún número suelto en el código: todo va en `perry/config/arm.yaml`.
- No inventes medidas ni pulsos. Si falta un dato, pídelo o déjalo en `null`.

## Qué hace el sistema

Tres robots:

- **Phineas** (recoge cubos azules) y **Ferb** (recoge cubos amarillos): robots móviles que dejan los cubos en una **zona azul** frente al brazo.
- **Perry**: brazo de 5 grados de libertad con pinza, controlado por una **Pololu Mini Maestro 12**. Ve el cubo con una cámara cenital (70 cm), lo toma y lo suelta: **amarillo → contenedor amarillo, azul → contenedor verde**. Los contenedores están uno a cada lado del brazo.

## Decisiones vigentes (13–14 de octubre de 2026)

- Raspberry Pi con **Raspbian de 64 bits** (ya configuradas, con OpenCV y pyserial).
- **Sin ROS 2, sin Docker, sin MoveIt.** Comunicación entre robots por **MQTT** (mosquitto + paho-mqtt), todavía sin implementar.
- **Python** en todo. El código C++ de `prueba/` se va a retirar (incluye un ejecutable x86 que no corre en la Pi).
- Visión: sustracción de fondo para encontrar el cubo (el cubo azul está sobre fondo azul) y HSV sobre el recorte para el color. YOLO solo si sobra tiempo.
- Brazo: cinemática inversa geométrica de la tesis de Miguel Lugo (UCAB, 2023, tutor Jesús Lárez). Es **el mismo modelo de brazo** (E2 = 10, E3 = 12 cm coinciden).

Documento completo: `docs/tecnologia.md`. Guía visual con dibujos, cálculo en vivo y hoja de registro: `Claude outputs/perry-coordenadas.html` (también publicada en claude.ai, privada de Ignacio).

## Medidas reales (14-10-2026)

| Medida | Valor |
| --- | --- |
| E1 mesa → eje del hombro | 3,3 cm |
| E2 hombro → codo | 10 cm |
| E3 codo → muñeca | 12 cm |
| E45 muñeca → punta de la pinza cerrada | 10,13 cm |
| Origen (eje de la base) → borde cercano de la zona | 9,3 cm |
| Zona | 13,5 cm de fondo (X) × 16,5 cm de ancho (Y) |
| Altura de agarre | 1 cm |

Sistema de coordenadas: origen en la mesa bajo el eje de giro de la base; X hacia el centro de la zona, Y a la izquierda, Z arriba.

**Alcance con la pinza vertical:** máximo 20,6 cm del eje. Con el hombro limitado a 90° (límite de la tesis), mínimo 11,8 cm. Por eso se definió una **franja de entrega entre 12 y 19,5 cm** del eje: ahí deben soltar los cubos Phineas y Ferb. El borde lejano de la zona (22,8 cm) no se alcanza.

## Código de Perry (`perry/`)

| Archivo | Qué hace |
| --- | --- |
| `config/arm.yaml` | Medidas, canales, calibración (`cal`: dos puntos [ángulo, pulso]), límites, pinza y poses fijas. Lo único que se edita al calibrar |
| `maestro.py` | Clase de Stalin ampliada: microsegundos, límites por canal, aceleración, `wait()` real (comando 0x93) |
| `kinematics.py` | `inverse_kinematics(x, y, z, links, cube_angle)` y `angle_to_us(joint, deg)` |
| `servo_cmd.py` | **Comandos sueltos, ideales para Claude Code**: `status`, `set CH US`, `nudge CH DELTA`, `pose NOMBRE` |
| `servo_jog.py` | Versión interactiva para una persona en la terminal |
| `pick_test.py` | Primer agarre sin cámara: `py pick_test.py 16 0 azul` (solo calcula) y con `--run` mueve |

Convenciones de ángulos (las mismas de la calibración): base 0° sobre el eje X, positivo a la izquierda; hombro desde la horizontal (90° = vertical); codo y muñeca como ángulos interiores (180° = recto); giro 0° con los dedos cerrando de izquierda a derecha. La pinza baja siempre vertical.

Canales según la tesis (verificar en el brazo real): base 0, hombro 2, codo 4, muñeca 6, giro 8, pinza 10.

La Maestro trabaja en cuartos de µs (1500 µs = 6000). El código del equipo usa µs; `codigo_python/main.py` de Stalin usa cuartos.

## Cómo correr en esta PC (Windows)

```
cd perry
$env:PERRY_PORT = "COM6"      # el puerto "Command Port" de la Maestro en el Administrador de dispositivos
py -m pip install pyserial pyyaml
py servo_cmd.py status
```

Maestro Control Center debe estar **cerrado** (ocupa el puerto). En la Maestro: modo serie USB Dual Port y límites de cada canal ampliados (por defecto recorta a 992–2000 µs).

## Reglas de seguridad al mover el brazo

1. **Pide confirmación antes de cada movimiento.** No encadenes movimientos sin que Ignacio lo vea.
2. Mueve **una articulación a la vez** y en pasos pequeños (≤ 50 µs) mientras se calibra.
3. Nunca mandes pulsos fuera de `min`/`max` de `arm.yaml`. Si un servo zumba o tiembla, es su límite: retrocede y anótalo.
4. Tú no ves el brazo: la posición la confirma Ignacio («listo», «un poco más»).
5. La primera corrida de `pick_test.py --run` se hace con la mano cerca del interruptor de la fuente.

## Dónde estamos y qué sigue

Hecho: medidas reales; `perry/` escrito; **primera sesión con el brazo real (14-10-2026)**:

- La Maestro aparece como **COM5** (Command Port) en la PC de Ignacio, no COM6. Los límites de los canales ya estaban ampliados en la Maestro.
- **Base calibrada**: 0° = 1470, 45° = 910, rango 520–2150, ~12,4 µs/° (bajar el pulso = izquierda). Llega a los dos contenedores: amarillo a ~54° izq., verde a ~50° der. (2100 deja la pinza sobre el verde).
- Con 1500 µs: hombro ≈ 110° (hacia atrás), codo ≈ 88°, muñeca ≈ 160°, giro ≈ 0°, pinza cerrada a medias.
- Hombro, codo y muñeca tienen una calibración **provisoria** medida con la webcam en diagonal: **falla**. En T2 a 6 cm de altura la pinza se pasa de largo y queda inclinada hacia afuera. Direcciones confirmadas: hombro, bajar el pulso = adelante (~5,6 µs/°, el más sensible); codo, bajar = abre; muñeca, subir = la pinza baja.
- Cámaras en la PC (OpenCV, `CAP_DSHOW`): índice 0 = webcam externa sobre la mesa (se mueve), índice 1 = cámara de la notebook.
- Al energizar un canal que está en 0 µs, salta de golpe: energizar de a uno, con el brazo sostenido.

Siguiente, en este orden:

1. **Recalibrar hombro, codo y muñeca con posturas enseñadas**: llevar la pinza con comandos a T1, T2 y T3 (vertical, a 1 cm, sobre la marca). La cinemática da el ángulo exacto de cada articulación en esa postura, y así cada postura aporta un par [ángulo, pulso]. Ajustar la recta con los tres puntos. Para ver bien conviene una cámara realmente de perfil (por ejemplo, el teléfono como webcam) y un fondo cuadriculado detrás del brazo. Faltan también el giro (0°/90°) y la pinza (abierta/cerrada).
2. **Puntos de prueba** T1 (12, 0), T2 (16, 0), T3 (19,5, 0), T4 (16, 6), T5 (16, −6): llevar la pinza vertical a 1 cm de la mesa y anotar pulsos. Compararlos con lo que da `pick_test.py` para validar la calibración. Confirmar si el hombro pasa de 90° sin forzarse.
3. **Poses fijas**: inicio, sobre contenedor amarillo, sobre contenedor verde.
4. **Primer agarre**: cubo a mano en (16, 0), `py pick_test.py 16 0 azul --run`.
5. Después: cámara a 70 cm, fotos de la zona, visión (`perry/vision.py`), y luego MQTT con Phineas y Ferb.

## Pendientes del repositorio

- Hacer commit de `perry/`, `docs/` y este archivo (todavía no están en Git).
- Retirar `prueba/` (C++ y binario) y crear el resto de la estructura de `docs/tecnologia.md`.
