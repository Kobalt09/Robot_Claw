# Guía de Prueba en Vivo (WSL 2 Manual) • Perry & Flota (Ferb)

Esta guía explica paso a paso cómo arrancar y probar manualmente la integración ROS 2 entre **Perry** y **Ferb** utilizando la distribución WSL 2 nativa (**`perry-ros`**).

---

## 🏗️ Arquitectura del Sistema

```
┌────────────────────────────────────────────────────────┐
│ WINDOWS (Laptop)                                      │
│  - Webcam LifeCam Studio + Pololu Maestro (COM5)       │
│  - audit_web.py en http://localhost:8000               │
│                                                        │
│  WSL 2 (perry-ros en modo mirrored: 10.253.102.98)     │
│  - ROS 2 Jazzy + Fast-DDS                              │
│  - perry_ros_bridge.py (comunica con audit_web.py)     │
└──────────────────────────▲─────────────────────────────┘
                           │ Wi-Fi paquidermos 4
┌──────────────────────────▼─────────────────────────────┐
│ FERB (Raspberry Pi: 10.253.102.198)                    │
│  - ROS 2 Jazzy/Lyrical + Fast-DDS                      │
│  - fleet_link / zone client                            │
└────────────────────────────────────────────────────────┘
```

---

## Paso 1: Levantar el Panel Web y Hardware en Windows

Abre una terminal de **PowerShell** en Windows y arranca el panel de Perry:

```powershell
python perry/audit_web.py
```

* Abre tu navegador en **`http://localhost:8000`** (o `http://10.253.102.98:8000`).
* Verifica que se vea la cámara cenital en la pestaña **Seguimiento en Vivo**.
* En los controles, presiona **`Habilitar Zona (FREE)`** cuando no haya cubos en la zona.

---

## Paso 2: Entrar a WSL 2 y Configurar el Entorno

Abre una **segunda terminal de PowerShell** e ingresa a la distro `perry-ros`:

```powershell
wsl -d perry-ros
```

Dentro de WSL, copia y pega este bloque para configurar las variables de entorno y limpiar proxies:

```bash
# 1. Limpiar variables de proxy que puedan bloquear localhost o DDS
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
export NO_PROXY="localhost,127.0.0.1,10.253.102.98,10.253.102.198"
export no_proxy="$NO_PROXY"

# 2. Cargar ROS 2 Jazzy y las interfaces multirobot
source /opt/ros/jazzy/setup.bash
source /opt/bridge_install/setup.bash

# 3. Configurar dominio y peers de la flota
export ROS_DOMAIN_ID=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_STATIC_PEERS=10.253.102.198
export PERRY_API=http://127.0.0.1:8000

# 4. Verificar que la IP de WSL coincida con tu Wi-Fi
hostname -I
```

> **Verificación:** `hostname -I` debe mostrar tu IP de la red Wi-Fi (ej. `10.253.102.98`).

---

## Paso 3: Arrancar el Puente ROS 2 de Perry

### Opción A: Ejecutar el script automático
```bash
bash /mnt/c/Users/crist/Documents/GitHub/Robot_Claw/docker/start_wsl_bridge.sh
```

### Opción B: Ejecutar manualmente con Python
```bash
python3 -u /mnt/c/Users/crist/Documents/GitHub/Robot_Claw/perry/perry_ros_bridge.py
```

**Salida esperada al iniciar:**
```text
[INFO] [perry_fleet_node]: Iniciando PerryRosBridge conectado a http://127.0.0.1:8000...
```
*(Mantén esta terminal abierta corriendo el bridge).*

---

## Paso 4: Monitoreo y Verificación Manual (Segunda Terminal WSL)

Abre una **tercera terminal de PowerShell** para interactuar con ROS 2 sin detener el bridge:

```powershell
wsl -d perry-ros
```
Carga el entorno:
```bash
source /opt/ros/jazzy/setup.bash
source /opt/bridge_install/setup.bash
export ROS_DOMAIN_ID=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_STATIC_PEERS=10.253.102.198
```

### 1. Ver nodos activos en la red
```bash
ros2 node list --no-daemon
```
*Debe aparecer `/perry/perry_fleet_node` y el nodo de Ferb `/ferb/fleet_link`.*

### 2. Ver tópicos activos
```bash
ros2 topic list --no-daemon
```
*Verás los tópicos de Perry (`/zone/occupant`, `/perry/state`, `/zone/gate_closed`) y los de Ferb (`/ferb/state`, `/ferb/zone/want`, `/ferb/zone/granted`).*

### 3. Escuchar el estado de Ferb en vivo
```bash
ros2 topic echo /ferb/state --no-daemon
```

### 4. Ver si Ferb está pidiendo la zona
```bash
ros2 topic echo /ferb/zone/want --no-daemon
```

---

## Paso 5: Probar los Servicios de Zona Manualmente

Puedes simular o forzar las llamadas de servicio tal como las hace Ferb:

### 1. Solicitar el turno de la zona (RequestZone)
```bash
ros2 service call /zone/request multirobot_interfaces/srv/RequestZone "{robot: 'ferb'}"
```
**Respuesta esperada:**
```yaml
granted: true
holder: 'ferb'
lease_seconds: 60.0
```
*(En el panel web verás que el ocupante pasa a ser `ferb`).*

### 2. Liberar la zona tras dejar un cubo (ReleaseZone)
```bash
ros2 service call /zone/release multirobot_interfaces/srv/ReleaseZone "{robot: 'ferb', delivered: true, color: 'blue'}"
```
**Respuesta esperada:**
```yaml
ok: true
delivered_count: 1
```
*(Perry pasará a estado `ASENTANDO` y luego clasificará el cubo automáticamente).*

---

## 🛠️ Diagnóstico y Solución de Problemas

1. **Si no se descubren nodos entre Perry y Ferb:**
   - Prueba multicast entre ambas máquinas:
     - En Perry: `ros2 multicast receive`
     - En Ferb: `ros2 multicast send`
   - Si no llega, verifica que `export ROS_STATIC_PEERS=10.253.102.198` esté definido en Perry y `export ROS_STATIC_PEERS=10.253.102.98` en Ferb.

2. **Si cambia la IP del Wi-Fi:**
   - Si se reconecta el router o cambian de red, revisa `hostname -I` y actualiza `ROS_STATIC_PEERS` con la nueva IP de Ferb.

3. **Hyper-V Firewall en Windows:**
   - Si las llamadas de servicio entrantes se bloquean, ejecuta en PowerShell de Windows como Administrador:
     ```powershell
     Set-NetFirewallHyperVVMSetting -Name '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -DefaultInboundAction Allow
     ```
