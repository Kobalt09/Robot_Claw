# Robot_Claw

Proyecto de Garra Robótica y Visión por Computadora diseñado para operar en **Raspberry Pi 4**.

---

## 📂 Estructura del Repositorio

- **[`codigo_python/`](codigo_python/)**: Sistema de visión por computadora modular en Python y utilidades del controlador.
  - [`detector_colores.py`](codigo_python/detector_colores.py): Clase `DetectorColores` para detección de 3 colores distintos (Rojo, Verde, Azul), extracción de contornos y cálculo de centroides $(C_x, C_y)$.
  - [`camara_stream.py`](codigo_python/camara_stream.py): Clase `CapturaCamara` optimizada para Raspberry Pi (V4L2, 640x480, multithreading sin latencia de búfer).
  - [`detector_en_vivo.py`](codigo_python/detector_en_vivo.py): Script de prueba en tiempo real con soporte dual para interfaz gráfica (GUI) o terminal por SSH (`--no-gui`).
  - [`maestro.py`](codigo_python/maestro.py): Módulo de comunicación serie con la controladora Pololu Maestro.
  - [`main.py`](codigo_python/main.py): Script de prueba de servomotores con Pololu Maestro.
  - [`requirements.txt`](codigo_python/requirements.txt): Dependencias de Python (`opencv-python`, `numpy`).
  - [`README.md`](codigo_python/README.md): Documentación detallada del módulo de visión, fórmulas de centroides y ejemplos de integración.
- **[`prueba/`](prueba/)**: Pruebas en C++ con OpenCV y modelos YOLO para visión y control multihilo.

---

## 🚀 Inicio Rápido (Visión en Raspberry Pi 4)

1. **Navegar a la carpeta de código Python**:
   ```bash
   cd codigo_python
   ```

2. **Instalar dependencias**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Ejecutar el detector de colores en vivo**:
   ```bash
   # Detección automática (ventana si hay pantalla, consola si es SSH)
   python3 detector_en_vivo.py

   # O forzar modo consola (ideal para SSH)
   python3 detector_en_vivo.py --no-gui
   ```

Para más detalles sobre la teoría de momentos para el cálculo de centroides y la integración modular en otros scripts, consulta el documento [`codigo_python/README.md`](codigo_python/README.md).
