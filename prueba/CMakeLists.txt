cmake_minimum_required(VERSION 3.10)
project(GarraRobotControl)

# Requerir estándar C++17
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Localizar la instalación de OpenCV
find_package(OpenCV REQUIRED)

# Incluir las cabeceras de OpenCV
include_directories(${OpenCV_INCLUDE_DIRS})

# Declarar el ejecutable y vincular bibliotecas
add_executable(garra_robot main.cpp)
target_link_libraries(garra_robot ${OpenCV_LIBS})
