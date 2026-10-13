#include <atomic>
#include <iostream>
#include <mutex>
#include <opencv2/opencv.hpp>
#include <thread>
#include <vector>

// --- RECURSOS COMPARTIDOS EN MEMORIA ---
cv::Mat frame_compartido;
std::mutex mutex_frame;

// Bandera atómica para detener los hilos de forma limpia
std::atomic<bool> ejecutando(true);

// --- MODELO YOLO (global, se inicializa en main) ---
cv::dnn::Net red_neuronal;

// Etiquetas COCO (80 clases de YOLOv8)
const std::vector<std::string> CLASES = {"red_block", "blue_block",
                                         "yellow_block"};

// ==========================================
// HILO 1: CAPTURA CONTINUA DE CÁMARA
// ==========================================
void hilo_camara() {
  cv::VideoCapture cap(0, cv::CAP_V4L2);

  if (!cap.isOpened()) {
    std::cerr << "[Cámara] Error al abrir la cámara.\n";
    ejecutando = false;
    return;
  }

  cap.set(cv::CAP_PROP_FRAME_WIDTH, 640);
  cap.set(cv::CAP_PROP_FRAME_HEIGHT, 480);

  cv::Mat temp_frame;

  while (ejecutando) {
    cap >> temp_frame;

    if (temp_frame.empty())
      continue;

    {
      std::lock_guard<std::mutex> lock(mutex_frame);
      temp_frame.copyTo(frame_compartido);
    }
  }

  cap.release();
  std::cout << "[Cámara] Hilo finalizado.\n";
}

// ==========================================
// HILO 2: CONTROL Y LÓGICA DEL ROBOT
// ==========================================
void posicion_base() {
  std::cout << "[Robot] Ejecutando posición base...\n";
  // Mover servomotores aquí
  std::this_thread::sleep_for(std::chrono::milliseconds(100));
}

// Estructura para guardar cada detección
struct Deteccion {
  std::string clase;
  float confianza;
  int cx, cy;    // Centro en píxeles
  cv::Rect bbox; // Bounding box completo
};

void escaneo() {
  cv::Mat foto_local;
  {
    std::lock_guard<std::mutex> lock(mutex_frame);
    if (!frame_compartido.empty())
      frame_compartido.copyTo(foto_local);
  }
  if (foto_local.empty())
    return;

  // --- Dimensiones originales del frame ---
  int img_w = foto_local.cols;
  int img_h = foto_local.rows;

  // 1. Preparar imagen para YOLOv8 (normalizar y redimensionar a 640x640)
  cv::Mat blob;
  cv::dnn::blobFromImage(foto_local, blob, 1.0 / 255.0, cv::Size(640, 640),
                         cv::Scalar(), /*swapRB=*/true, /*crop=*/false);
  red_neuronal.setInput(blob);

  // 2. Inferencia → salida shape: [1, 84, 8400]
  //    84 = 4 coords (cx,cy,w,h) + 80 clases COCO
  cv::Mat salida = red_neuronal.forward();

  // 3. Parsear detecciones
  // Reorganizar de [1, 84, 8400] a [8400, 84] para iterar por detección
  cv::Mat datos = salida.reshape(1, salida.size[1]).t(); // → [8400, 84]

  const float UMBRAL_CONFIANZA = 0.5f;
  const float UMBRAL_NMS = 0.45f;

  std::vector<cv::Rect> bboxes;
  std::vector<float> confianzas;
  std::vector<int> ids_clase;

  for (int i = 0; i < datos.rows; i++) {
    float *fila = datos.ptr<float>(i);

    // Las primeras 4 columnas: cx, cy, w, h (en coordenadas del espacio
    // 640x640)
    float cx_norm = fila[0];
    float cy_norm = fila[1];
    float w_norm = fila[2];
    float h_norm = fila[3];

    // Columnas 4..83: puntuaciones de cada clase
    cv::Mat puntuaciones(1, (int)CLASES.size(), CV_32F, fila + 4);
    cv::Point id_clase_pt;
    double confianza;
    cv::minMaxLoc(puntuaciones, nullptr, &confianza, nullptr, &id_clase_pt);

    if (confianza < UMBRAL_CONFIANZA)
      continue;

    // Escalar coordenadas de 640x640 al tamaño real del frame
    float escala_x = (float)img_w / 640.0f;
    float escala_y = (float)img_h / 640.0f;

    int x = (int)((cx_norm - w_norm / 2.0f) * escala_x);
    int y = (int)((cy_norm - h_norm / 2.0f) * escala_y);
    int w = (int)(w_norm * escala_x);
    int h = (int)(h_norm * escala_y);

    bboxes.push_back(cv::Rect(x, y, w, h));
    confianzas.push_back((float)confianza);
    ids_clase.push_back(id_clase_pt.x);
  }

  // 4. Non-Maximum Suppression (elimina detecciones duplicadas)
  std::vector<int> indices;
  cv::dnn::NMSBoxes(bboxes, confianzas, UMBRAL_CONFIANZA, UMBRAL_NMS, indices);

  // 5. Publicar y dibujar resultados
  std::vector<Deteccion> detecciones;

  for (int idx : indices) {
    cv::Rect bbox = bboxes[idx];
    int clase_id = ids_clase[idx];
    float conf = confianzas[idx];

    // ── COORDENADAS DEL CENTRO DEL OBJETO ──
    int cx = bbox.x + bbox.width / 2;
    int cy = bbox.y + bbox.height / 2;

    std::string nombre_clase =
        (clase_id < (int)CLASES.size()) ? CLASES[clase_id] : "desconocido";

    detecciones.push_back({nombre_clase, conf, cx, cy, bbox});

    std::cout << "[YOLO] Objeto: " << nombre_clase
              << " | Confianza: " << (int)(conf * 100) << "%"
              << " | Centro: (" << cx << ", " << cy << ")"
              << " | BBox: [" << bbox.x << "," << bbox.y << "  " << bbox.width
              << "x" << bbox.height << "]\n";

    // Dibujar bounding box y etiqueta
    cv::rectangle(foto_local, bbox, cv::Scalar(0, 255, 0), 2);
    cv::circle(foto_local, cv::Point(cx, cy), 5, cv::Scalar(0, 0, 255), -1);

    std::string etiqueta =
        nombre_clase + " " + std::to_string((int)(conf * 100)) + "%";
    cv::putText(foto_local, etiqueta, cv::Point(bbox.x, bbox.y - 8),
                cv::FONT_HERSHEY_SIMPLEX, 0.55, cv::Scalar(0, 255, 0), 2);
  }

  cv::imshow("Vista Robot - YOLO", foto_local);
  cv::waitKey(1);
}

void hilo_robot() {
  while (ejecutando) {
    posicion_base();
    escaneo();
  }
  cv::destroyAllWindows();
  std::cout << "[Robot] Hilo finalizado.\n";
}

// ==========================================
// PROGRAMA PRINCIPAL
// ==========================================
int main() {
  std::cout << "Iniciando sistema multihilo para Garra Robot...\n";

  // Cargar modelo YOLOv8 ANTES de lanzar los hilos
  std::cout << "[Main] Cargando modelo YOLO...\n";
  red_neuronal = cv::dnn::readNetFromONNX("yolov8n.onnx");

  if (red_neuronal.empty()) {
    std::cerr << "[Main] ERROR: No se pudo cargar yolov8n.onnx\n";
    return 1;
  }

  // Usar GPU si está disponible (CUDA), si no → CPU
  red_neuronal.setPreferableBackend(cv::dnn::DNN_BACKEND_OPENCV);
  red_neuronal.setPreferableTarget(cv::dnn::DNN_TARGET_CPU);

  std::cout << "[Main] Modelo cargado correctamente.\n";

  // Lanzar los dos hilos en paralelo
  std::thread t_camara(hilo_camara);
  std::thread t_robot(hilo_robot);

  std::cout << "Presione ENTER para detener la ejecución...\n";
  std::cin.get();

  // Detener ambos hilos
  ejecutando = false;

  if (t_camara.joinable())
    t_camara.join();
  if (t_robot.joinable())
    t_robot.join();

  std::cout << "Sistema apagado correctamente.\n";
  return 0;
}