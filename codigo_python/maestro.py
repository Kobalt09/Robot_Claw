import serial

class Maestro:
    """
    Controlador para la tarjeta de servos Pololu Maestro.
    """
    def __init__(self, port, timeout=1):
        """Inicializa la conexión serie con el Maestro."""
        self.ser = serial.Serial(port, timeout=timeout)

    def close(self):
        """Cierra el puerto serie de forma segura."""
        if self.ser.is_open:
            self.ser.close()

    def get_position(self, channel):
        """Obtiene la posición actual de un canal."""
        command = bytes([0x90, channel])
        self.ser.write(command)
        
        response = self.ser.read(2)
        if len(response) != 2:
            raise Exception(f"Error leyendo el canal {channel}. ¿Está conectado el Maestro?")
        
        return response[0] + 256 * response[1]

    def set_target(self, channel, target):
        """Establece el objetivo de un canal (en cuartos de microsegundo)."""
        command = bytes([0x84, channel, target & 0x7F, (target >> 7) & 0x7F])
        self.ser.write(command)

    def set_speed(self, channel, speed):
        """
        Establece el límite de velocidad de un canal.
        (0 = sin límite/velocidad máxima)
        """
        command = bytes([0x87, channel, speed & 0x7F, (speed >> 7) & 0x7F])
        self.ser.write(command)

    # --- Métodos mágicos para usar la clase con bloques 'with' ---
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
