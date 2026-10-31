# Perry (brazo)

Perry ve los cubos con la cámara cenital, los agarra y los deja en su contenedor
(azul → verde, amarillo → amarillo). Todo número vive en `config/arm.yaml`.

## Correr el clasificador

```
cd perry
$env:PERRY_PORT = "COM5"          # Windows: el "Command Port" de la Maestro. En la Pi: /dev/ttyACM0
py sort_cubes.py                  # solo mira: lista los cubos y qué haría
py sort_cubes.py --run            # clasifica hasta vaciar la zona
py sort_cubes.py --run --to amarillo   # todo a un contenedor (pruebas)
```

Antes: Maestro Control Center **cerrado** (ocupa el puerto), fuente de los servos encendida.
Si los servos están en 0 µs (recién encendidos), el primer pulso los hace saltar: acomodar
el brazo a mano cerca de la pose `vista` y energizar de a uno con `servo_cmd.py set`.

Cada corrida deja registro y fotos en `logs/AAAA-MM-DD_HH-MM-SS/`.

### Qué hace el ciclo
1. Estaciona el brazo arriba y a la derecha (pose `vista`) para no tapar la cámara.
2. Busca cubos **solo dentro del rectángulo** de la zona (`camera.zone`).
3. Si un cubo está fuera de la tabla enseñada (`reach.rows`), avisa y lo **ignora**.
4. Abre la pinza, llega **por arriba** con la base llegando siempre desde abajo (juego de ~7°),
   gira la pinza según el cubo y baja el hombro **lento** (`descent_speed`).
5. Cierra, sube en vertical, vuelve a mirar: si el cubo sigue ahí, el agarre falló y reintenta
   (`sort.retries`); luego lo da por perdido.
6. Va al contenedor por arriba y suelta.

## Auditar y convertir fallas en tests

Cada corrida guarda en `logs/<corrida>/` las fotos, `registro.txt` y **`ciclos.jsonl`**: por ciclo,
los cubos vistos, la decisión (agarrar / empujar) y si el agarre salió.

```
py replay.py logs/<corrida>                         # qué decidiría HOY el planificador en cada ciclo
py replay.py guardar logs/<corrida> 3 grab --color amarillo --nota "pegado a un azul"
py -m pytest tests                                  # incluye todas las escenas guardadas
```

`guardar` copia la escena a `tests/scenes/`: desde ese momento, si un cambio rompe ese caso, los tests
fallan. Regla del equipo: **cada falla que se entienda en la mesa se guarda como escena** con lo que
debería haber hecho.

## Si algo cambió

| Pasó esto | Hacer |
| --- | --- |
| Movieron la cámara cenital | `py calibrate_camera.py`: clic en las 4 esquinas del rectángulo |
| La cámara cambió de número | `camera.index` en `arm.yaml` (0 o 1) |
| Agarra alto o se clava en la mesa | `reach.grip_shoulder_offset_us` (más negativo = baja más) |
| Falla siempre a cierta distancia | Enseñar una fila nueva en `reach.rows` (ver abajo) |
| Suelta el cubo en el aire | `gripper.closed` un poco más alto (1700 = cerrada del todo) |
| No detecta un color | Rangos HSV en `camera.colors` |

### Enseñar una fila de `reach.rows`
Con un cubo a la distancia r (cm) del eje: `py servo_cmd.py goto X Y bajar ÁNGULO`, mirar de
costado y de frente, y corregir con `py servo_cmd.py set 2 …` (hombro), `set 4 …` (codo),
`set 6 …` (muñeca) hasta que el cubo quede entre los dedos con la pinza vertical.
Probar con `set 10 1600` + `up`. Anotar `{r, hombro, codo, muneca}` (sin el offset del resorte:
sumarle de vuelta `grip_shoulder_offset_us` al hombro).

## Archivos

| Archivo | Para qué |
| --- | --- |
| `config/arm.yaml` | Medidas, calibración, tabla enseñada, poses, cámara. Lo único que se edita |
| `sort_cubes.py` | El ciclo automático completo |
| `vision.py` | Cámara cenital, homografía píxel → cm, detección (usa `codigo_python/`) |
| `calibrate_camera.py` | Rehacer la homografía si mueven la cámara |
| `reach.py` | Tabla enseñada (r → hombro, codo, muñeca), movimientos por arriba, juego de la base |
| `servo_cmd.py` | Comandos sueltos: `status`, `set`, `nudge`, `pose`, `up`, `goto X Y [bajar] [ángulo]` |
| `maestro.py` | Habla con la Pololu (basado en la clase de Stalin), en microsegundos y con límites |
| `kinematics.py` | Cinemática inversa (tesis de Lugo) y conversión ángulo → pulso por tramos |
| `servo_jog.py` | Mover un servo a mano desde la terminal |
| `pick_test.py` | Primer agarre sin cámara (histórico; usa la cinemática, no la tabla) |

En la Pi: `sudo apt install -y python3-yaml` (OpenCV y pyserial ya están).
