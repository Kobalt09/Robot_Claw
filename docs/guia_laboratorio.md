# Perry en el laboratorio: guía paso a paso

Para levantar Perry en la Raspberry Pi sin ayuda. Los comandos se escriben en **Git Bash en la PC**, salvo
que diga «en la Pi». Rama: `feat/perry-integracion`.

## 0. Qué llevar

- [ ] La PC con el repo actualizado (`git pull`) y, si vas a usar Docker sin internet, el archivo
      `docker/perry_claw_lyrical_arm64.tar.gz` (se genera en casa con `bash docker/save_image.sh`).
- [ ] Cable de red para conectar **directo** la PC con la Pi.
- [ ] Fuente de los servos y fuente de la Pi (5 V, 3 A, USB-C).
- [ ] Cubos azules y amarillos.

## 1. Encender la Pi (sin USB)

1. Con la **Maestro y la webcam desconectadas**, enchufá la alimentación de la Pi.
   > Si están conectadas al encender, la Pi no arranca (LED verde apagado).
2. Esperá 1 minuto. El LED verde tiene que parpadear de a ratos.
3. Conectá el cable de red **directo** de la PC a la Pi. La PC sale a internet por Wi-Fi.
4. Si usás ProtonVPN: dejá activado el túnel dividido con la IP `169.254.49.182` excluida.

Comprobá la conexión:

```bash
ssh manipulador@169.254.49.182 "uptime"
```

Si no responde, mirá la sección **Si algo falla**.

## 2. Conectar el brazo y la cámara

1. Con la Pi **ya encendida**, conectá el USB de la Maestro y el de la webcam cenital.
   **No muevas la cámara**: si se mueve, hay que recalibrarla (sección 6).
2. Comprobá que la Pi los ve:

```bash
ssh manipulador@169.254.49.182 "ls /dev/ttyACM*; vcgencmd get_throttled"
```

   Tiene que aparecer `/dev/ttyACM0`, y `throttled=0x0` quiere decir que no hubo caídas de tensión.

## 3. Energizar los servos (con el brazo sostenido)

Al encender, los servos están sueltos (0 µs). Encendé la fuente de los servos y **sostené el brazo arriba y
girado a la derecha**. Después, de a uno:

```bash
ssh manipulador@169.254.49.182 "cd ~/Robot_Claw_perry/perry && python3 servo_cmd.py set 2 1450 && python3 servo_cmd.py set 4 1300 && python3 servo_cmd.py set 6 2000 && python3 servo_cmd.py set 0 2100 && python3 servo_cmd.py set 8 1447 && python3 servo_cmd.py set 10 750"
```

Si preferís ir de a uno para ver cada movimiento, corré cada `set` por separado.
Comprobá con `python3 servo_cmd.py status`: ningún canal debe quedar en 0.

## 4. Levantar Perry

Elegí **un** camino.

### A. Con ROS 2, para la flota (Docker)

```bash
bash docker/deploy_pi.sh
```

Copia el código, carga la imagen por el cable si la Pi no la tiene y levanta el contenedor. La primera vez
tarda varios minutos en pasar la imagen. Si la Pi tiene internet, usá `BUILD=1 bash docker/deploy_pi.sh`.

### B. Solo el brazo, sin ROS (el plan de respaldo, ya probado)

```bash
git archive HEAD perry codigo_python docs | ssh manipulador@169.254.49.182 "cd ~/Robot_Claw_perry && tar -xmf -"
```

```bash
ssh manipulador@169.254.49.182 'cd ~/Robot_Claw_perry/perry && (setsid nohup python3 audit_web.py > ~/perry_panel.log 2>&1 < /dev/null &)'
```

En los dos casos, el panel queda en **http://169.254.49.182:8000**.

## 5. Probar antes de la demo

1. En el panel: **Solo mirar**. Tiene que dibujar los cubos donde están.
2. Un solo cubo en la franja verde y **Iniciar**. Mano cerca de la fuente de los servos.
3. Opcional: **Prueba de precisión** con un solo cubo. Esperado: unos 3 mm (umbral: 5 mm).
4. Para la flota: **Habilitar zona (FREE)** y, desde la Pi de un carro, en la misma red y con `ROS_DOMAIN_ID=0`:

```bash
ros2 topic echo /zone/occupant
```

   Tiene que mostrar `data: ''` dos veces por segundo, y `"perry"` mientras la zona está cerrada.

## 6. Si algo falla

| Qué pasa | Qué hacer |
| --- | --- |
| `ssh` no responde, o «Network is unreachable» | Revisá que el cable vaya directo PC–Pi (no a la red de la UCAB). Ejecutá `ipconfig`: el puerto Ethernet tiene que tener una IP `169.254.x.x` |
| La Pi no arranca (verde apagado) | Desconectá los USB, desenchufá 5 s y encendé solo con la alimentación |
| `throttled` distinto de `0x0` | La fuente de la Pi no alcanza: usá una de 3 A o un hub USB con fuente |
| Un servo salta al energizarlo | Normal si estaba en 0 µs: siempre con el brazo sostenido |
| El panel no abre la cámara | `camera.index` en `perry/config/arm.yaml` (0 o 1) |
| Los cubos aparecen corridos | Movieron la cámara: pestaña **Calibrar cámara** del panel, marcá las 4 esquinas del **azul** (lejana izq., lejana der., cercana der., cercana izq.) |
| Agarra alto o se clava en la mesa | `reach.grip_shoulder_offset_us` en `arm.yaml` (más negativo = baja más) |
| Dos agarres fallados seguidos | Se detiene a propósito: correr **Prueba de precisión** |
| La zona queda cerrada (BLOCKED) sin motivo | Revisá que no haya nada grande en el azul; después, **Habilitar zona** |
| Docker no arranca, o los carros no ven a Perry | Usá el camino B para la demo del brazo. Revisá con `docker compose logs` en `~/Robot_Claw_perry` |
| Hay que usar `servo_cmd.py` con Docker corriendo | Primero `docker compose down` (los dos usan la Maestro) |

## 7. Respaldo: la versión probada del 31-10

La etiqueta `perry-probado-31-10` es la última versión que corrió con el brazo real, antes de la integración
con ROS 2. Si la versión integrada se comporta distinto, se vuelve a ella.

Clonarla aparte, sin tocar tu copia de trabajo:

```bash
git clone --branch perry-probado-31-10 https://github.com/Kobalt09/Robot_Claw.git Robot_Claw_probado
```

Llevarla a la Pi y abrir su panel. Desde la carpeta del clon; primero se detiene el panel o el contenedor que
esté corriendo:

```bash
ssh manipulador@169.254.49.182 'cd ~/Robot_Claw_perry && (docker compose down 2>/dev/null; pkill -f "^python3 audit_web.py"; true)'
```

```bash
git archive perry-probado-31-10 perry codigo_python | ssh manipulador@169.254.49.182 "mkdir -p ~/Robot_Claw_probado && tar -xmf - -C ~/Robot_Claw_probado"
```

```bash
ssh manipulador@169.254.49.182 'cd ~/Robot_Claw_probado/perry && (setsid nohup python3 audit_web.py > ~/perry_panel.log 2>&1 < /dev/null &)'
```

Va en otra carpeta de la Pi (`~/Robot_Claw_probado`), así que no pisa la integrada. El panel queda en la
misma dirección: http://169.254.49.182:8000.

## 8. Al terminar

1. Con el brazo sostenido, apagá la fuente de los servos.
2. Si usaste Docker: `ssh manipulador@169.254.49.182 "cd ~/Robot_Claw_perry && docker compose down"`.
3. Desconectá la Pi. Las fotos y los registros de cada corrida quedan en la Pi, en
   `~/Robot_Claw_perry/perry/logs/`.
