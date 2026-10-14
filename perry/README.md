# Perry (brazo)

| Archivo | Para qué |
| --- | --- |
| `config/arm.yaml` | Medidas, canales, calibración y posiciones. Lo único que se edita al calibrar |
| `maestro.py` | Habla con la Pololu (basado en la clase de Stalin), en microsegundos y con límites |
| `kinematics.py` | Cinemática inversa (tesis de Lugo) y conversión de grados a pulsos |
| `servo_jog.py` | Mover un servo a mano y ver sus pulsos (`p` muestra todos) |
| `pick_test.py` | Primer agarre automático sin cámara |

En la Pi: `sudo apt install -y python3-yaml` (OpenCV y pyserial ya están).

Orden de uso:
1. `python3 servo_jog.py` y llenar la hoja de registro (guía visual, sección 5).
2. Pasar los pulsos a `config/arm.yaml` (reemplazar los `null`).
3. `python3 pick_test.py 16 0 azul` para ver el cálculo sin mover nada.
4. `python3 pick_test.py 16 0 azul --run` con un cubo en (16, 0).
