#include <iostream>
#include <thread>
#include <mutex>
#include <atomic>
#include <opencv2/opencv.hpp>

// --- RECURSOS COMPARTIDOS EN MEMORIA ---
cv::Mat frame_compartido;
std::mutex mutex_frame;

// Bandera atómica para detener los hilos de forma limpia
std::atomic<bool> ejecutando(true);

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
        // 1. Lee la imagen física del sensor
        cap >> temp_frame;

        if (temp_frame.empty()) continue;

        // 2. Protege el acceso a la memoria compartida mientras copia la imagen
        {
            std::lock_guard<std::mutex> lock(mutex_frame);
            temp_frame.copyTo(frame_compartido);
        } // El mutex se libera automáticamente al salir de este bloque
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
    std::this_thread::sleep_for(std::chrono::milliseconds(100)); // Simula tiempo de movimiento
}

void escaneo() {
    cv::Mat foto_local;

    // Obtener la imagen más reciente cargada por el hilo de la cámara
    {
        std::lock_guard<std::mutex> lock(mutex_frame);
        if (!frame_compartido.empty()) {
            frame_compartido.copyTo(foto_local);
        }
    }

    // Si tenemos una foto válida, la procesamos o mostramos
    if (!foto_local.empty()) {
        std::cout << "[Robot] Procesando fotograma en etapa de escaneo...\n";
        cv::imshow("Vista Robot", foto_local);
        cv::waitKey(1); // Mantiene la ventana activa sin congelar el flujo
    }
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

    // Lanzar los dos hilos en paralelo
    std::thread t_camara(hilo_camara);
    std::thread t_robot(hilo_robot);

    std::cout << "Presione ENTER para detener la ejecución...\n";
    std::cin.get();

    // Detener ambos hilos
    ejecutando = false;

    // Esperar a que los hilos terminen limpiamente antes de salir
    if (t_camara.joinable()) t_camara.join();
    if (t_robot.joinable()) t_robot.join();

    std::cout << "Sistema apagado correctamente.\n";
    return 0;
}