# Dockerfile para Perry (Robot_Claw)
# Entorno de ROS 2 para la Raspberry Pi y PCs de desarrollo
ARG BASE_IMAGE=ros:jazzy-ros-base
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Instalar dependencias del sistema y librerías de Python requeridas para Perry
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-opencv \
    python3-serial \
    python3-yaml \
    python3-numpy \
    python3-pip \
    build-essential \
    cmake \
    git \
    v4l-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ws

# Script de entrada para compilación de interfaces y arranque
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "audit_web.py"]
