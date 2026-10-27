# Sistema Modular de Detección de Colores con OpenCV (Raspberry Pi 4)

Este paquete implementa un sistema modular de visión artificial con OpenCV optimizado para **Raspberry Pi 4**, diseñado para:
1. Capturar video en tiempo real desde una cámara USB o cámara Raspberry Pi (v4l2).
2. Reconocer simultáneamente **tres colores distintos** (Rojo, Verde y Azul).
3. Marcar sus **contornos** exteriores en la imagen.
4. Calcular sus **centroides** $(C_x, C_y)$ mediante momentos espaciales de imagen.
5. Permitir su invocación modular desde cualquier script o controlador externo.

---

## 📁 Archivos del Módulo

| Archivo | Descripción |
| :--- | :--- |
| [`detector_colores.py`](detector_colores.py) | **Módulo central de detección**: Contiene la clase `DetectorColores` y la estructura `DeteccionColor`. Realiza segmentación HSV, operaciones morfológicas, extracción de contornos y cálculo de centroides. |
| [`camara_stream.py`](camara_stream.py) | **Módulo de captura de cámara**: Contiene la clase `CapturaCamara`. Optimizado para Raspberry Pi 4 con `v4l2`, resolución 640x480, búfer de 1 frame y captura en hilo dedicado para eliminar lag. |
| [`detector_en_vivo.py`](detector_en_vivo.py) | **Script ejecutable de prueba**: Ejecuta la cámara en tiempo real, detecta los colores y muestra los contornos, centroides y datos en pantalla o consola. |
| [`requirements.txt`](requirements.txt) | Dependencias de Python (`opencv-python`, `numpy`). |

---

## 📐 Cálculo del Centroide

El centroide geométrico $(C_x, C_y)$ representa el centro de masa de la figura detectada. Se calcula a partir de los **momentos espaciales de la imagen** (`cv2.moments`):

$$M_{pq} = \sum_{x} \sum_{y} x^p \cdot y^q \cdot I(x, y)$$

Donde los momentos clave son:
- **$M_{00}$**: Área total del contorno (número total de píxeles activos).
- **$M_{10}$**: Suma acumulada de las coordenadas horizontales $x$.
- **$M_{01}$**: Suma acumulada de las coordenadas verticales $y$.

Las coordenadas del centroide se obtienen mediante:

$$C_x = \frac{M_{10}}{M_{00}}, \quad C_y = \frac{M_{01}}{M_{00}}$$

En el código ([`detector_colores.py`](detector_colores.py)), se valida además que $M_{00} \neq 0$ para evitar indeterminaciones o divisiones por cero en contornos degenerados o ruido.

---

## 🚀 Uso Modular desde Scripts Externos

Puedes importar el detector y la cámara directamente en cualquier script:

```python
from detector_colores import DetectorColores
from camara_stream import CapturaCamara

# 1. Inicializar detector y cámara
detector = DetectorColores(area_minima=600)
camara = CapturaCamara(indice_camara=0, ancho=640, alto=480, usar_hilo=True)

# 2. Capturar frame
exito, frame = camara.leer_frame()

if exito and frame is not None:
    # 3. Procesar detecciones (colores, contornos y centroides)
    detecciones = detector.procesar_frame(frame)

    for det in detecciones:
        print(f"Color detectado: {det.color}")
        print(f"Centroide (cx, cy): ({det.cx}, {det.cy})")
        print(f"Área del contorno: {det.area} px")
        print(f"Bounding box: {det.bbox}")

    # 4. (Opcional) Dibujar contornos y centroides sobre la imagen
    frame_anotado = detector.dibujar_detecciones(frame, detecciones)

# 5. Liberar recursos al finalizar
camara.liberar()
```

---

## 🎨 Configuración de Colores HSV

El detector incluye por defecto 3 colores preconfigurados:
- **Rojo (`rojo`)**: Maneja el salto angular del tono (Hue) en HSV mediante dos sub-rangos (`[0, 120, 70] - [10, 255, 255]` y `[170, 120, 70] - [180, 255, 255]`).
- **Verde (`verde`)**: `[36, 80, 50]` a `[85, 255, 255]`.
- **Azul (`azul`)**: `[95, 100, 50]` a `[130, 255, 255]`.

Para agregar un nuevo color dinámicamente desde código externo:
```python
import numpy as np

detector.configurar_color(
    nombre="amarillo",
    rangos_hsv=[(np.array([20, 100, 100]), np.array([35, 255, 255]))],
    color_bgr=(0, 255, 255)
)
```

---

## ⚙️ Instalación y Ejecución en Raspberry Pi 4

### 1. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 2. Ejecución

- **Modo automático (detecta si hay pantalla o SSH)**:
  ```bash
  python3 detector_en_vivo.py
  ```
- **Modo consola forzado (recomendado para terminales SSH sin entorno gráfico)**:
  ```bash
  python3 detector_en_vivo.py --no-gui
  ```
- **Si estás conectado por SSH y quieres que la ventana aparezca en el monitor HDMI de la Raspberry Pi**:
  ```bash
  export DISPLAY=:0
  python3 detector_en_vivo.py
  ```
