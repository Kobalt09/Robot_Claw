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

Documento completo: `docs/tecnologia.md`. Guía visual con dibujos, cálculo en vivo y hoja de registro: `docs/perry-coordenadas.html` (también publicada en claude.ai, privada de Ignacio).

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

**Sesiones del 20 y 27-10-2026: Perry clasifica solo** (`perry/sort_cubes.py --run`; ver `perry/README.md`).

- Hombro, codo y muñeca ya no usan la cinemática: **tabla enseñada** `reach.rows` (r → pulsos), probada con cubos reales a 16 y 18 cm.
- Base calibrada por tramos con puntos tocados (0° = 1504), con **~7° de juego**: se llega siempre desde abajo.
- El giro de la pinza tenía el **signo invertido** (corregido). El resorte nuevo del hombro sube el brazo: `grip_shoulder_offset_us: -30`.
- Visión: cámara cenital + homografía con las 4 esquinas del rectángulo (16,5 × 8,5 cm, X de 11,1 a 19,6 cm); usa el detector de Stalin (`codigo_python/`). Si mueven la cámara: `calibrate_camera.py`.
- Probado: cubos girados, cubo fuera de alcance (lo ignora), agarre fallido (lo detecta y reintenta).
- Pendiente: enseñar con cubo real las filas de ~13,8 y ~20 cm (a 14 cm del lado izquierdo el primer agarre a veces falla); contenedor verde y qué hacer con el cubo rojo; precisión del giro en cubos muy girados; probar en la Raspberry.

**Sesión del 28-10-2026: panel web y grupos de cubos** (estado para quien continúe)

- **Cómo se opera:** `cd perry; $env:PERRY_PORT="COM5"; py audit_web.py` → http://localhost:8000. Botones Iniciar / Paso a paso / Solo mirar / Cancelar, cámara en vivo, decisión dibujada y registro. Calibrar la cámara desde la pestaña del panel. Fotos y registro de cada corrida en `perry/logs/`.
- **Al encender:** los servos arrancan en 0 µs. Acomodar el brazo a mano (arriba y girado a la derecha) y energizar de a uno: `py servo_cmd.py set 2 1450`, `set 4 1300`, `set 6 2000`, `set 0 2100`, `set 8 1447`, `set 10 750`.
- **Cámara cenital: índice 1** (cambia al reconectar; si sale negra o es la de la notebook, cambiar `camera.index`). Cajas: amarilla a la izquierda, verde a la derecha. Azules → caja amarilla, amarillos → caja verde.
- `grasp.py` (con tests: `py -m pytest perry/tests`) decide agarrar por un eje libre o empujar en cualquier dirección; `vision.py` separa cubos pegados (área + k-means) y corrige la paralaje (cámara a 70 cm). Fila de alcance nueva a 11,9 cm.
- **Probado y descartado:** arrastrar un cubo apoyando la pinza desde arriba (patina o fuerza el hombro). Los racimos apretados no tienen solución práctica: **decisión: los rastrillos deben dejar los cubos separados** (una fila, ~1,5 cm entre cubos, entre 12 y 19,5 cm del eje).
- **Dato:** la pinza cierra del todo recién en ~2350 µs (1700 deja ~1,5 cm entre puntas).
- **Siguiente:** estado "ZONA BLOQUEADA" + aviso MQTT a Phineas y Ferb; documento de requisitos para los equipos de los rastrillos; checklist de fallas; probar en la Raspberry.
- **DroidCam:** no conecta si el teléfono tiene una VPN activa.

**Sesión del 31-10-2026: precisión medida y zona azul real**

- **Cámara cenital: índice 0** (cambia al reconectar). Calibración de la cámara rehecha (`camera.corners_px`); sigue valiendo aunque se quite la milimetrada, mientras no muevan la cámara.
- **Zona azul real:** su fondo es H 103–104 y los cubos azules H 113–124. El rango `azul` arranca en **109**. Con otra iluminación puede requerir ajuste; lo robusto sería la sustracción de fondo.
- **Prueba de precisión** (`precision.py` o el botón del panel): mide el error del brazo con "cerrar y soltar" en 5 puntos. Con ella se recalibró la base a 5 puntos y el error medio bajó de **6,4 a 3,0 mm** (Lugo: 1,2 mm). Correrla cuando se sospeche desajuste; resultados en `logs/precision/`.
- **Escenas como tests:** cada corrida guarda `ciclos.jsonl`; `py replay.py logs/<corrida>` repite con el planificador actual, y `py replay.py guardar …` convierte una falla en test (`tests/scenes/`). 51 tests: `py -m pytest perry/tests`.
- Planificador: margen lateral de los dedos 0,1 cm; no agarra si entre los dedos puede quedar un cubo de **otro** color (del mismo sí); empujes perpendiculares primero; empuja con la pinza cerrada del todo (2350); el tope de empujes es por atasco. Después de agarrar va **directo a la caja** y verifica al final.
- **Última corrida:** 4 de 4 cubos al primer intento; 2 ignorados a 19,5 y 20,5 cm (fuera de alcance). **La zona azul llega a ~22,8 cm y el brazo a 19,5**: los carros deben soltar los cubos entre 12 y 19,5 cm del eje (convendría marcar esa franja).
- Pendiente: medir el extremo izquierdo de la base (+36,6°); explicar un Cancelar que llegó sin que nadie lo apretara (ahora se registra la IP); estado ZONA BLOQUEADA con aviso MQTT; requisitos escritos para los equipos de los carros; probar en la Raspberry.

**Tarde del 31-10-2026: Perry corre en la Raspberry y propuesta de comunicación** (estado para quien continúe)

- **Cámara recalibrada con las esquinas del AZUL de la zona** (sin las cintas verdes), porque se retiró la milimetrada. Los cm se midieron con la calibración anterior: X de 11,5 a 21,5, Y de −8,4 a 8,1 (el azul visible mide ~10 × 16,5 cm; la tabla de 13,5 cm de arriba incluye lo que tapan las cintas). **Si mueven la cámara, solo cambian `camera.corners_px`** (las 4 esquinas del azul en la imagen). Verificado agarrando un cubo.
- **Perry corre en la Pi** (Raspberry Pi 4, 4 GB, Debian 13, sin internet). Código en `~/Robot_Claw_perry` (se copia con `git archive HEAD perry codigo_python docs | ssh … tar -xmf -`). Acceso: `ssh manipulador@169.254.49.182`, con cable directo PC–Pi (la PC sale a internet por Wi-Fi; con ProtonVPN, excluir esa IP en el túnel dividido). Panel: `cd ~/Robot_Claw_perry/perry && setsid nohup python3 audit_web.py > ~/perry_panel.log 2>&1 < /dev/null &` → `http://169.254.49.182:8000`.
- En la Pi: Maestro en `/dev/ttyACM0` (valor de `arm.yaml`), webcam en el índice 0. Ya tiene todo instalado (OpenCV, pyserial, PyYAML, pytest, Docker). **No arranca si la Maestro y la webcam están conectadas al encender**: conectarlas después, o usar un hub USB con fuente. Al arrancar, los servos quedan en 0 µs: energizar de a uno con los pulsos de la postura en que está el brazo. El reloj está atrasado (~200 días): las carpetas de `logs/` salen con fecha falsa.
- **Primera corrida en la Pi:** 5 cubos clasificados, 25–28 s por cubo (igual que en la PC), sin caídas de tensión, 46 °C, carga 1,2, 344 MB. La Pi no es el cuello de botella.
- **Arreglo:** un empuje en cadena dejó un cubo a 11,7 cm (fuera de alcance; el previsto era 12,2). Ahora los cubos empujados quedan a `push_margin_r` de **los dos** bordes del alcance; test de invariante sobre todas las escenas.
- **Comunicación con los carros:** su contrato es ROS 2 (`multirobot_interfaces`: llave de la zona `/zone/request`, `/zone/release`, latido `/zone/occupant`), pero **hoy ninguna Pi tiene ROS** y los carros corren scripts de laboratorio sin árbitro. Cristian hizo la parte ROS de Perry con Docker en la rama `mejoras-de-portabilidad` (Jazzy; los carros van a Lyrical). **Propuesta enviada:** el mismo contrato por HTTP desde la Pi de Perry (`docs/comunicacion_flota.md`), con comportamiento definido en `docs/perry_zona_estados.md` (una sola llave para carros y brazo; Perry cierra la zona quedándose con la llave; colores pedidos). Foto de la franja de entrega: `docs/diagramas/zona_franja_entrega.jpg`.
- **Siguiente:** respuesta de los equipos a las 7 decisiones de la propuesta; árbitro HTTP como proceso aparte con tests y un «carro simulado»; detector de «zona despejada» (objeto grande o ArUco); estado ZONA CERRADA en el panel; red común con IP fija para Perry.

Siguiente (plan original, ya superado en parte):

1. **Recalibrar hombro, codo y muñeca con posturas enseñadas**: llevar la pinza con comandos a T1, T2 y T3 (vertical, a 1 cm, sobre la marca). La cinemática da el ángulo exacto de cada articulación en esa postura, y así cada postura aporta un par [ángulo, pulso]. Ajustar la recta con los tres puntos. Para ver bien conviene una cámara realmente de perfil (por ejemplo, el teléfono como webcam) y un fondo cuadriculado detrás del brazo. Faltan también el giro (0°/90°) y la pinza (abierta/cerrada).
2. **Puntos de prueba** T1 (12, 0), T2 (16, 0), T3 (19,5, 0), T4 (16, 6), T5 (16, −6): llevar la pinza vertical a 1 cm de la mesa y anotar pulsos. Compararlos con lo que da `pick_test.py` para validar la calibración. Confirmar si el hombro pasa de 90° sin forzarse.
3. **Poses fijas**: inicio, sobre contenedor amarillo, sobre contenedor verde.
4. **Primer agarre**: cubo a mano en (16, 0), `py pick_test.py 16 0 azul --run`.
5. Después: cámara a 70 cm, fotos de la zona, visión (`perry/vision.py`), y luego MQTT con Phineas y Ferb.

## Pendientes del repositorio

- Hacer commit de `perry/`, `docs/` y este archivo (todavía no están en Git).
- Retirar `prueba/` (C++ y binario) y crear el resto de la estructura de `docs/tecnologia.md`.
