# Perry en Docker (ROS 2 Lyrical)

El contenedor corre el panel de Perry (`perry/audit_web.py`), que levanta el árbitro de la zona y el
nodo ROS 2 (`/zone/occupant`, `/zone/request`, `/zone/release`, `/perry/state`), con **ROS 2 Lyrical**,
la misma distribución que Phineas y Ferb. La Pi de Perry tiene Debian 13, sin paquetes de ROS: por eso
va en Docker.

- `network_mode: host`, `ROS_DOMAIN_ID=0`: los carros ven a Perry en la red como si no hubiera contenedor.
- El código **se monta** como volumen (`.:/ws`): para actualizarlo no hace falta reconstruir la imagen.
- Al arrancar, `entrypoint.sh` compila `src/multirobot_interfaces` y abre el panel en el puerto 8000.

## Llevarlo a la Pi

Hay dos caminos. Los dos se manejan desde la PC, por SSH (cable directo: `manipulador@169.254.49.182`).

### A. La Pi tiene internet (Wi-Fi)

```bash
BUILD=1 bash docker/deploy_pi.sh
```

Copia el código, construye la imagen en la Pi (15–25 min la primera vez) y levanta el contenedor.

### B. La Pi NO tiene internet (lo habitual: solo el cable)

En la PC, con Docker Desktop abierto (una sola vez, o cuando cambie el `Dockerfile`):

```bash
bash docker/save_image.sh
```

Construye la imagen para arm64 **emulando** el procesador de la Pi (lento) y la guarda en
`docker/perry_claw_lyrical_arm64.tar.gz` (no va a Git). Después, con la Pi en el cable:

```bash
bash docker/deploy_pi.sh
```

Copia el código, pasa la imagen por el cable y levanta el contenedor.

## Uso diario en la Pi

```bash
cd ~/Robot_Claw_perry
docker compose up -d          # levantar (también arranca solo al encender: restart unless-stopped)
docker compose logs -f        # ver qué hace
docker compose down           # parar (por ejemplo, para usar servo_cmd.py a mano)
```

Antes de levantarlo:
- **Conectar la Maestro y la webcam DESPUÉS de encender la Pi** (si están conectadas al encender, no arranca).
- Los servos arrancan en 0 µs: energizarlos con el brazo sostenido (ver `CLAUDE.md`).
- El panel nativo (`python3 audit_web.py`) no puede estar corriendo a la vez (usa el mismo puerto, la
  Maestro y la cámara). `deploy_pi.sh` lo detiene.

## Comprobar que los carros lo ven

Desde la Pi de Phineas o Ferb, en la misma red y con `ROS_DOMAIN_ID=0`:

```bash
ros2 topic echo /zone/occupant    # "perry" al arrancar (zona cerrada hasta «Habilitar zona»)
ros2 topic echo /perry/state      # gate_closed: true hasta habilitar
```
