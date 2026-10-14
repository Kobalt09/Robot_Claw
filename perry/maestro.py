"""Control de la Pololu Maestro por USB.

Basado en la clase Maestro de Stalin (codigo_python/maestro.py). Se agregan:
- trabajar en microsegundos (us), que es lo que se anota al calibrar;
- límites de seguridad por canal (nunca se manda un pulso fuera de rango);
- aceleración y espera real a que los servos terminen de moverse.

La Maestro trabaja internamente en cuartos de microsegundo: 1500 us = 6000.
"""
import time
import serial


class Maestro:
    def __init__(self, port="/dev/ttyACM0", timeout=1, limits=None):
        self.ser = serial.Serial(port, timeout=timeout)
        # limits: {canal: (min_us, max_us)}
        self.limits = limits or {}

    def close(self):
        if self.ser.is_open:
            self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # --- comandos crudos (cuartos de microsegundo) ---
    def get_position(self, channel):
        self.ser.write(bytes([0x90, channel]))
        r = self.ser.read(2)
        if len(r) != 2:
            raise IOError(f"Sin respuesta del canal {channel}. ¿Está conectada la Maestro?")
        return r[0] + 256 * r[1]

    def set_target(self, channel, target):
        self.ser.write(bytes([0x84, channel, target & 0x7F, (target >> 7) & 0x7F]))

    def set_speed(self, channel, speed):
        self.ser.write(bytes([0x87, channel, speed & 0x7F, (speed >> 7) & 0x7F]))

    def set_acceleration(self, channel, accel):
        self.ser.write(bytes([0x89, channel, accel & 0x7F, (accel >> 7) & 0x7F]))

    def is_moving(self):
        """True mientras algún servo no haya llegado a su objetivo."""
        self.ser.write(bytes([0x93]))
        r = self.ser.read(1)
        return bool(r and r[0])

    # --- en microsegundos, con límites ---
    def get_us(self, channel):
        return self.get_position(channel) / 4

    def set_us(self, channel, us):
        lo, hi = self.limits.get(channel, (500, 2500))
        if not lo <= us <= hi:
            clamped = min(max(us, lo), hi)
            print(f"  [aviso] canal {channel}: {us:.0f} us fuera de [{lo}, {hi}], se usa {clamped:.0f}")
            us = clamped
        self.set_target(channel, int(round(us * 4)))

    def wait(self, timeout=8.0):
        """Espera a que todos los servos lleguen. Devuelve False si se agotó el tiempo."""
        t0 = time.time()
        while self.is_moving():
            if time.time() - t0 > timeout:
                return False
            time.sleep(0.05)
        return True
