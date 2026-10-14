import time
from maestro import Maestro # Importa la clase que acabas de crear

def main():
    puerto = 'COM6'  # Cambia a '/dev/ttyACM0' si estás en Linux
    canal = 0

    try:
        # El bloque 'with' asegura que puerto se cierre solo al terminar
        with Maestro(port=puerto) as servo_ctrl:
            print("Conectado al Pololu Maestro.")
            
            # 1. Ajustar la velocidad
            servo_ctrl.set_speed(canal, 60)
            print(f"Velocidad ajustada a 60 en el canal {canal}.")
            
            # 2. Leer la posición actual
            posicion = servo_ctrl.get_position(canal)
            print(f"La posición actual es {posicion}.")
            
            # 3. Mover a un nuevo objetivo
            nuevo_objetivo = 7000 if posicion < 6000 else 5000
            print(f"Moviendo al objetivo {nuevo_objetivo}...")
            servo_ctrl.set_target(canal, nuevo_objetivo)
            
            # Esperar a que el servo llegue a su destino
            time.sleep(1)
            print("Movimiento completado.")

    except Exception as e:
        print(f"Error de comunicación: {e}")

if __name__ == "__main__":
    main()
