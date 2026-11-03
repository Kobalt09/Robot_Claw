"""ASENTANDO: cuándo puede Perry mover el brazo después de que un carro devolvió la llave.

Que el carro devuelva la llave no prueba que se fue (puede haber quedado trabado con la pala adentro).
Perry espera tres cosas (docs/perry_zona_estados.md, sección 4):
  1. zona despejada: ningún objeto grande dentro del azul (vision.zone_is_clear);
  2. escena quieta: dos cuadros seguidos casi iguales;
  3. un tiempo mínimo desde la devolución (settle.min_s).
Si en settle.max_s no se cumple, la zona se cierra (BLOCKED) y una persona la revisa.
Lógica pura (sin cámara ni ROS): se prueba en tests/test_settle.py.
"""


class Settler:
    def __init__(self, t0, min_s, max_s):
        self.t0, self.min_s, self.max_s = t0, min_s, max_s
        self.result = None      # "go" o "blocked" una vez decidido
        self.reason = ""

    def update(self, now, clear, still):
        """Devuelve "wait", "go" o "blocked". Una vez que decide, no cambia."""
        if self.result:
            return self.result
        elapsed = now - self.t0
        if not clear:
            self.reason = "hay un objeto grande en la zona (¿un carro?)"
        elif not still:
            self.reason = "hay movimiento en la zona"
        elif elapsed < self.min_s:
            self.reason = f"esperando el mínimo de {self.min_s:.0f} s"
        else:
            self.result, self.reason = "go", "zona despejada y quieta"
            return self.result
        if elapsed >= self.max_s:
            self.result = "blocked"
            self.reason = f"la zona no se despejó en {self.max_s:.0f} s: {self.reason}"
            return self.result
        return "wait"
