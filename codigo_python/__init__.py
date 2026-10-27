"""
Módulos de visión por computadora con OpenCV.
Permite importar fácilmente DetectorColores, DeteccionColor y CapturaCamara.
"""

from .detector_colores import DetectorColores, DeteccionColor
from .camara_stream import CapturaCamara

__all__ = ["DetectorColores", "DeteccionColor", "CapturaCamara"]
