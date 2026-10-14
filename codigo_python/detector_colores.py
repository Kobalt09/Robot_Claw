"""
detector_colores.py
===================
Módulo de visión por computadora para detección de tres colores distintos,
marcado de contornos y cálculo de centroides usando OpenCV.
Diseñado para ser modular y ejecutarse de manera eficiente en Raspberry Pi 4.
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict


@dataclass
class DeteccionColor:
    """
    Estructura de datos que almacena la información de un objeto detectado.
    
    Atributos:
        color (str): Nombre del color detectado ('rojo', 'verde', 'azul', etc.).
        centroide (Tuple[int, int]): Coordenadas (cx, cy) del centro de masa en píxeles.
        contorno (np.ndarray): Puntos del contorno del objeto.
        area (float): Área del contorno en píxeles cuadrados.
        bbox (Tuple[int, int, int, int]): Cuadro delimitador (x, y, w, h).
        color_bgr (Tuple[int, int, int]): Color BGR sugerido para dibujar en pantalla.
    """
    color: str
    centroide: Tuple[int, int]
    contorno: np.ndarray
    area: float
    bbox: Tuple[int, int, int, int]
    color_bgr: Tuple[int, int, int]

    @property
    def cx(self) -> int:
        """Coordenada X del centroide."""
        return self.centroide[0]

    @property
    def cy(self) -> int:
        """Coordenada Y del centroide."""
        return self.centroide[1]


class DetectorColores:
    """
    Clase modular para la detección de múltiples colores mediante segmentación HSV,
    filtrado morfológico, cálculo de contornos y obtención de centroides mediante momentos.
    """

    def __init__(
        self,
        area_minima: float = 600.0,
        area_maxima: Optional[float] = None,
        ksize_desenfoque: Tuple[int, int] = (5, 5),
        ksize_morfologia: Tuple[int, int] = (5, 5),
    ):
        """
        Inicializa el detector de colores.

        Parámetros:
            area_minima: Filtro para descartar ruido pequeño (en píxeles cuadrados).
            area_maxima: Filtro opcional para descartar objetos excesivamente grandes o fondos.
            ksize_desenfoque: Tamaño del kernel Gaussiano para suavizar la imagen y reducir ruido.
            ksize_morfologia: Tamaño del kernel para operaciones de apertura y cierre morfológico.
        """
        self.area_minima = area_minima
        self.area_maxima = area_maxima
        self.ksize_desenfoque = ksize_desenfoque
        
        # Kernel elíptico para operaciones morfológicas (más natural para contornos físicos)
        self.kernel_morf = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, ksize_morfologia)

        # Diccionario de rangos HSV preconfigurados para 3 colores principales
        # Formato: lista de tuplas (np.array([H_min, S_min, V_min]), np.array([H_max, S_max, V_max]))
        # Nota: En OpenCV, H va de 0 a 179, S de 0 a 255 y V de 0 a 255.
        self.rangos_colores: Dict[str, Dict] = {}
        self._cargar_rangos_predeterminados()

    def _cargar_rangos_predeterminados(self):
        """
        Configura los rangos iniciales en espacio HSV para Rojo, Verde y Azul.
        El rojo requiere dos rangos debido a que el tono (Hue) cruza el origen (0/180).
        """
        # 1. COLOR ROJO:
        # En HSV el rojo está tanto al inicio [0, 10] como al final del rango [170, 180]
        self.configurar_color(
            nombre="rojo",
            rangos_hsv=[
                (np.array([0, 120, 70], dtype=np.uint8), np.array([10, 255, 255], dtype=np.uint8)),
                (np.array([170, 120, 70], dtype=np.uint8), np.array([180, 255, 255], dtype=np.uint8)),
            ],
            color_bgr=(0, 0, 255)  # Rojo para dibujar
        )

        # 2. COLOR VERDE:
        # Tono típico verde entre 36 y 85
        self.configurar_color(
            nombre="verde",
            rangos_hsv=[
                (np.array([36, 80, 50], dtype=np.uint8), np.array([85, 255, 255], dtype=np.uint8))
            ],
            color_bgr=(0, 255, 0)  # Verde para dibujar
        )

        # 3. COLOR AZUL:
        # Tono típico azul entre 95 y 130
        self.configurar_color(
            nombre="azul",
            rangos_hsv=[
                (np.array([95, 100, 50], dtype=np.uint8), np.array([130, 255, 255], dtype=np.uint8))
            ],
            color_bgr=(255, 0, 0)  # Azul para dibujar
        )

    def configurar_color(
        self,
        nombre: str,
        rangos_hsv: List[Tuple[np.ndarray, np.ndarray]],
        color_bgr: Tuple[int, int, int] = (255, 255, 255)
    ):
        """
        Permite agregar o actualizar un color y sus rangos HSV desde código externo.

        Parámetros:
            nombre: Identificador del color ('rojo', 'verde', 'azul', etc.).
            rangos_hsv: Lista de pares (limite_inferior, limite_superior) en HSV.
            color_bgr: Color en formato BGR para dibujar contornos y textos.
        """
        self.rangos_colores[nombre.lower()] = {
            "rangos": rangos_hsv,
            "color_bgr": color_bgr
        }

    def obtener_mascara(self, frame_hsv: np.ndarray, nombre_color: str) -> Optional[np.ndarray]:
        """
        Genera la máscara binaria para un color específico, combinando múltiples
        rangos si es necesario (como en el caso del rojo).
        """
        info_color = self.rangos_colores.get(nombre_color.lower())
        if not info_color:
            return None

        mascara_total = None
        for (inf, sup) in info_color["rangos"]:
            mascara_parcial = cv2.inRange(frame_hsv, inf, sup)
            if mascara_total is None:
                mascara_total = mascara_parcial
            else:
                mascara_total = cv2.bitwise_or(mascara_total, mascara_parcial)

        # Filtrado morfológico para optimizar detección en la Raspberry Pi 4:
        # 1. MORPH_OPEN (Erosión seguida de Dilatación): Elimina píxeles aislados de ruido.
        # 2. MORPH_CLOSE (Dilatación seguida de Erosión): Cierra pequeños agujeros dentro del objeto.
        mascara_total = cv2.morphologyEx(mascara_total, cv2.MORPH_OPEN, self.kernel_morf)
        mascara_total = cv2.morphologyEx(mascara_total, cv2.MORPH_CLOSE, self.kernel_morf)

        return mascara_total

    def procesar_frame(self, frame: np.ndarray) -> List[DeteccionColor]:
        """
        Procesa una imagen/frame capturado para identificar los colores configurados,
        obtener sus contornos y calcular sus centroides.

        Parámetros:
            frame: Imagen BGR obtenida de la cámara (NumPy array).

        Retorna:
            Lista de objetos DeteccionColor con la información de cada detección válida.
        """
        if frame is None or frame.size == 0:
            return []

        # 1. Suavizado gaussiano para reducir ruido de alta frecuencia del sensor
        suavizado = cv2.GaussianBlur(frame, self.ksize_desenfoque, 0)

        # 2. Conversión del espacio de color BGR a HSV
        frame_hsv = cv2.cvtColor(suavizado, cv2.COLOR_BGR2HSV)

        detecciones: List[DeteccionColor] = []

        # 3. Iterar sobre cada color configurado
        for nombre_color, datos_color in self.rangos_colores.items():
            mascara = self.obtener_mascara(frame_hsv, nombre_color)
            if mascara is None:
                continue

            # 4. Encontrar contornos externos del objeto
            # Usamos cv2.RETR_EXTERNAL para detectar solo el contorno exterior del objeto
            # Usamos cv2.CHAIN_APPROX_SIMPLE para ahorrar memoria y CPU en la Raspberry Pi
            contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contorno in contornos:
                area = cv2.contourArea(contorno)

                # Filtrar contornos por tamaño mínimo y máximo para ignorar ruido o fondos
                if area < self.area_minima:
                    continue
                if self.area_maxima is not None and area > self.area_maxima:
                    continue

                # 5. Cálculo del centroide mediante momentos espaciales de la imagen
                # cx = M10 / M00, cy = M01 / M00
                momentos = cv2.moments(contorno)
                if momentos["m00"] != 0:
                    cx = int(momentos["m10"] / momentos["m00"])
                    cy = int(momentos["m01"] / momentos["m00"])
                else:
                    # Alternativa de respaldo en caso degenerado
                    cx, cy = 0, 0

                # Bounding box rectangular (x, y, ancho, alto)
                bbox = cv2.boundingRect(contorno)

                detecciones.append(
                    DeteccionColor(
                        color=nombre_color,
                        centroide=(cx, cy),
                        contorno=contorno,
                        area=area,
                        bbox=bbox,
                        color_bgr=datos_color["color_bgr"]
                    )
                )

        return detecciones

    def obtener_objeto_principal(
        self,
        detecciones: List[DeteccionColor],
        color: Optional[str] = None
    ) -> Optional[DeteccionColor]:
        """
        Función auxiliar: devuelve el objeto detectado con mayor área,
        opcionalmente filtrando por un color específico.
        """
        candidatos = detecciones
        if color is not None:
            candidatos = [d for d in detecciones if d.color.lower() == color.lower()]

        if not candidatos:
            return None

        # El objeto de mayor área suele ser el más cercano o prominente
        return max(candidatos, key=lambda d: d.area)

    def dibujar_detecciones(
        self,
        frame: np.ndarray,
        detecciones: List[DeteccionColor],
        dibujar_contorno: bool = True,
        dibujar_centroide: bool = True,
        dibujar_bbox: bool = True,
        dibujar_etiquetas: bool = True
    ) -> np.ndarray:
        """
        Dibuja los contornos, centroides y etiquetas informativas sobre una copia del frame.

        Parámetros:
            frame: Imagen original sobre la cual dibujar.
            detecciones: Lista de detecciones obtenidas de procesar_frame().
            dibujar_contorno: Si es True, dibuja el borde exterior del objeto.
            dibujar_centroide: Si es True, dibuja un círculo y cruz en el centroide.
            dibujar_bbox: Si es True, dibuja una caja delimitadora rectangular.
            dibujar_etiquetas: Si es True, escribe el nombre del color y coordenadas (cx, cy).

        Retorna:
            Imagen anotada resultante.
        """
        resultado = frame.copy()

        for det in detecciones:
            color_bgr = det.color_bgr

            # 1. Dibujar contorno exterior
            if dibujar_contorno:
                cv2.drawContours(resultado, [det.contorno], -1, color_bgr, 2)

            # 2. Dibujar cuadro delimitador (Bounding Box)
            x, y, w, h = det.bbox
            if dibujar_bbox:
                cv2.rectangle(resultado, (x, y), (x + w, y + h), color_bgr, 1, cv2.LINE_AA)

            # 3. Dibujar centroide (círculo rojo/blanco y cruz)
            if dibujar_centroide:
                cx, cy = det.centroide
                # Círculo relleno en el centro
                cv2.circle(resultado, (cx, cy), 5, (0, 0, 255), -1)
                # Cruz pequeña para máxima precisión visual
                cv2.line(resultado, (cx - 10, cy), (cx + 10, cy), (255, 255, 255), 1)
                cv2.line(resultado, (cx, cy - 10), (cx, cy + 10), (255, 255, 255), 1)

            # 4. Dibujar texto con nombre del color y coordenadas del centroide
            if dibujar_etiquetas:
                cx, cy = det.centroide
                texto = f"{det.color.upper()} ({cx},{cy})"
                pos_y = max(20, y - 8)
                
                # Fondo negro para mejorar legibilidad del texto en pantalla
                (tw, th), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(resultado, (x, pos_y - th - 4), (x + tw + 4, pos_y + 4), (0, 0, 0), -1)
                
                cv2.putText(
                    resultado,
                    texto,
                    (x + 2, pos_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA
                )

        return resultado
