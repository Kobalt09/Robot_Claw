"""
camara_stream.py
================
Módulo de captura de video con OpenCV optimizado para Raspberry Pi 4 y Linux.
Proporciona captura directa o mediante hilo dedicado (multithreading) para eliminar
la latencia del búfer de la cámara y maximizar los FPS.
"""

import sys
import threading
import time
import cv2
import numpy as np
from typing import Tuple, Optional


class CapturaCamara:
    """
    Gestiona la captura de video desde cámara USB o módulo CSI (v4l2)
    minimizando la latencia en Raspberry Pi.
    """

    def __init__(
        self,
        indice_camara: int = 0,
        ancho: int = 640,
        alto: int = 480,
        fps: int = 30,
        usar_hilo: bool = True
    ):
        """
        Inicializa la cámara con parámetros optimizados.

        Parámetros:
            indice_camara: ID del dispositivo de video (/dev/video0 -> 0).
            ancho: Resolución horizontal (640 recomendado para RPi 4).
            alto: Resolución vertical (480 recomendado para RPi 4).
            fps: Cuadros por segundo deseados.
            usar_hilo: Si es True, ejecuta la lectura en segundo plano para evitar retrasos de búfer.
        """
        self.indice = indice_camara
        self.ancho = ancho
        self.alto = alto
        self.fps = fps
        self.usar_hilo = usar_hilo

        # En Linux / Raspberry Pi se recomienda cv2.CAP_V4L2 para menor sobrecarga
        backend = cv2.CAP_V4L2 if sys.platform.startswith("linux") else cv2.CAP_ANY

        self.cap = cv2.VideoCapture(self.indice, backend)
        if not self.cap.isOpened():
            # Intento de respaldo con backend estándar
            self.cap = cv2.VideoCapture(self.indice)

        if not self.cap.isOpened():
            raise RuntimeError(f"[CapturaCamara] No se pudo abrir la cámara en el índice {indice_camara}.")

        # Configuración de resolución y formato
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.ancho)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.alto)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        # En Raspberry Pi, reducir el tamaño del búfer a 1 evita frames atrasados
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Variables para manejo de hilo
        self.corriendo = False
        self.frame_actual: Optional[np.ndarray] = None
        self.bloqueo = threading.Lock()
        self.hilo: Optional[threading.Thread] = None

        if self.usar_hilo:
            self._iniciar_hilo()

    def _iniciar_hilo(self):
        """Inicia el hilo secundario para captura continua."""
        self.corriendo = True
        self.hilo = threading.Thread(target=self._bucle_captura, daemon=True)
        self.hilo.start()
        # Pequeña pausa para asegurar la captura del primer frame
        time.sleep(0.2)

    def _bucle_captura(self):
        """Bucle infinito que mantiene siempre el último frame fresco en memoria."""
        while self.corriendo and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret and frame is not None:
                with self.bloqueo:
                    self.frame_actual = frame
            else:
                time.sleep(0.005)

    def leer_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Obtiene el frame más reciente capturado.

        Retorna:
            (exito, frame): Tupla donde exito es un booleano y frame es el np.ndarray BGR.
        """
        if self.usar_hilo:
            with self.bloqueo:
                if self.frame_actual is not None:
                    return True, self.frame_actual.copy()
                return False, None
        else:
            return self.cap.read()

    def liberar(self):
        """Detiene el hilo y libera el dispositivo de captura."""
        self.corriendo = False
        if self.hilo and self.hilo.is_alive():
            self.hilo.join(timeout=1.0)

        if self.cap and self.cap.isOpened():
            self.cap.release()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.liberar()
