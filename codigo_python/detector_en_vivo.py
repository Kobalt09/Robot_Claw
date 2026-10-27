"""
detector_en_vivo.py
===================
Script ejecutable para prueba en tiempo real del reconocimiento de
3 colores, contornos y centroides con cámara en Raspberry Pi 4.

Soporta ejecución con interfaz gráfica (GUI) o en modo consola (Headless / SSH).

Uso:
    python3 detector_en_vivo.py             (Detección automática de pantalla)
    python3 detector_en_vivo.py --no-gui    (Forzar modo terminal sin ventanas)

Autor: Proyecto Garra Robot
"""

import os
import sys
import time
import argparse
import cv2

# Importamos las clases modulares desarrolladas
from detector_colores import DetectorColores
from camara_stream import CapturaCamara


def verificar_servidor_grafico() -> bool:
    """
    Verifica si existe un display X11 o Wayland disponible en el entorno.
    Evita que OpenCV / Qt colapsen con 'could not connect to display' al ejecutar vía SSH.
    """
    display = os.environ.get("DISPLAY")
    wayland = os.environ.get("WAYLAND_DISPLAY")
    return bool(display or wayland)


def parsear_argumentos():
    parser = argparse.ArgumentParser(description="Detección de 3 colores con OpenCV en Raspberry Pi 4")
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Ejecuta en modo consola sin abrir ventanas gráficas (recomendado para SSH / headless)."
    )
    parser.add_argument(
        "--camara",
        type=int,
        default=0,
        help="Índice del dispositivo de video (por defecto 0 -> /dev/video0)."
    )
    return parser.parse_args()


def main():
    args = parsear_argumentos()

    print("=" * 60)
    print("  INICIANDO SISTEMA DE VISIÓN - DETECCIÓN DE 3 COLORES")
    print("  Optimizado para Raspberry Pi 4")
    print("=" * 60)

    # Determinar si se puede y debe mostrar ventana gráfica
    servidor_grafico_activo = verificar_servidor_grafico()
    mostrar_gui = (not args.no_gui) and servidor_grafico_activo

    if not mostrar_gui:
        if args.no_gui:
            print("[INFO] Modo consola forzado mediante --no-gui.")
        else:
            print("[AVISO] No se detectó servidor gráfico (DISPLAY no configurado o sesión SSH).")
            print("        Ejecutando en modo consola (Headless). Los centroides se mostrarán en la terminal.")
            print("        (Si tienes monitor conectado a la RPi, ejecuta: 'export DISPLAY=:0')")
    else:
        print("[INFO] Servidor gráfico detectado. Se abrirá ventana de visualización.")

    # 1. Instanciar detector modular
    detector = DetectorColores(area_minima=600)
    print(f"Colores configurados: {list(detector.rangos_colores.keys())}")
    print("Conectando cámara...")

    # 2. Inicializar captura de cámara
    try:
        camara = CapturaCamara(indice_camara=args.camara, ancho=640, alto=480, fps=30, usar_hilo=True)
    except Exception as e:
        print(f"[ERROR] No se pudo inicializar la cámara: {e}")
        sys.exit(1)

    print("Cámara lista. Presione Ctrl+C (o 'q' en ventana) para salir.\n")
    t_previo = time.time()
    contador_frames = 0
    fps_estimado = 0.0

    try:
        while True:
            # 3. Lectura de nuevo frame
            exito, frame = camara.leer_frame()
            if not exito or frame is None:
                time.sleep(0.01)
                continue

            contador_frames += 1
            t_actual = time.time()
            if (t_actual - t_previo) >= 1.0:
                fps_estimado = contador_frames / (t_actual - t_previo)
                contador_frames = 0
                t_previo = t_actual

            # 4. Procesamiento modular: Detección de colores, contornos y centroides
            detecciones = detector.procesar_frame(frame)

            # 5. Imprimir centroides y datos en terminal
            if detecciones:
                for det in detecciones:
                    print(
                        f"[{det.color.upper()}] "
                        f"Centroide: ({det.cx:3d}, {det.cy:3d}) | "
                        f"Área: {det.area:7.1f} px | "
                        f"BBox: [x={det.bbox[0]}, y={det.bbox[1]}, w={det.bbox[2]}, h={det.bbox[3]}] | "
                        f"FPS: {fps_estimado:.1f}"
                    )

            # 6. Visualización gráfica solo si hay display activo
            if mostrar_gui:
                frame_visual = detector.dibujar_detecciones(frame, detecciones)
                cv2.putText(
                    frame_visual,
                    f"FPS: {fps_estimado:.1f}",
                    (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 255),
                    2
                )

                try:
                    cv2.imshow("Deteccion de 3 Colores - OpenCV", frame_visual)
                    tecla = cv2.waitKey(1) & 0xFF
                    if tecla == ord('q') or tecla == 27:
                        print("Salida solicitada por el usuario.")
                        break
                except Exception as err_gui:
                    print(f"[Aviso GUI] Error al mostrar ventana ({err_gui}). Continuando en modo consola...")
                    mostrar_gui = False
            else:
                # En modo sin GUI, pequeña pausa para no saturar CPU innecesariamente
                time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nInterrupción manual (Ctrl+C). Deteniendo...")

    finally:
        camara.liberar()
        if mostrar_gui:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
        print("Recursos liberados correctamente.")


if __name__ == "__main__":
    main()
