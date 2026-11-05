# Guía Rápida de Laboratorio: Perry en Laptop (Opción 1)

Esta guía te permite encender y coordinar a **Perry** directamente desde tu laptop con **Windows**, la garra en `COM5`, la cámara **Microsoft LifeCam Studio** y la red **ROS 2** en Docker para sincronizarse con los carros (**Ferb** y **Phineas**).

---

## 1. Conexiones Físicas (Hardware)

1. **Cámara**: Conecta la **Microsoft LifeCam Studio** al puerto USB de tu laptop.
2. **Controlador Maestro**: Conecta el cable USB del **Pololu Mini Maestro 12** a tu laptop (puerto `COM5`).
3. **Alimentación Servos**: Enciende la fuente de poder externa de los servos (5V - 6V, ~3A-5A).
   > **Importante**: Sostén el brazo suavemente si los servos caen por gravedad hasta que se energicen.

---

## 2. Red Wi-Fi del Laboratorio

1. Conecta tu laptop a la **misma red Wi-Fi** donde estén conectados los carros Ferb y Phineas (el router dedicado del laboratorio o el hotspot).
2. Verifica tu IP local en la terminal de Windows:
   ```powershell
   ipconfig
   ```
   *(Anota tu dirección IPv4, por ejemplo `192.168.1.50`, si tus compañeros quieren abrir tu panel web desde sus laptops o teléfonos).*

---

## 3. Paso 1: Levantar el Panel Web y Control de Hardware (Windows)

Abre una terminal de **PowerShell** en la carpeta del proyecto y ejecuta:

```powershell
python perry/audit_web.py
```

* Abre tu navegador en: **`http://localhost:8000`**
* **Verificaciones en pantalla**:
  - Pestaña **Seguimiento**: Debe verse el video en vivo de la cámara cenital y el contorno verde de la zona de entrega.
  - Tarjeta **Perry**: Debe indicar `STOP` o `listo`.

---

## 4. Paso 2: Levantar la Red ROS 2 en Docker

Abre una **segunda terminal** en la misma carpeta y ejecuta:

```powershell
docker compose -f compose_bridge.yaml up -d
```

*(Si ya estaba levantado y cambiaste de Wi-Fi, ejecuta `docker compose -f compose_bridge.yaml restart`).*

Para verificar que el nodo de ROS 2 arrancó y enlazó con el panel web:
```powershell
docker logs --tail 10 perry_ros_bridge
```
> Debe mostrar: `[perry_fleet_node]: Iniciando PerryRosBridge conectado a http://172.25.32.1:8000...`

---

## 5. Paso 3: Habilitar la Zona para los Carros

1. Asegúrate de que **no haya cubos en la zona de entrega** y que el brazo esté en reposo (`vista`).
2. En el panel web (`http://localhost:8000`), haz clic en el botón verde:
   👉 **`Habilitar Zona (FREE)`**
3. El estado de Perry cambiará a **`FREE`** y `perry-occ` mostrará `ZONA LIBRE ("")`.
4. A partir de este momento, **Ferb** y **Phineas** tienen permiso de solicitar la llave y entrar a dejar sus cubos.

---

## 6. Comandos para tus compañeros de Ferb y Phineas

Tus compañeros en sus Raspberry Pi deben tener:
```bash
export ROS_DOMAIN_ID=0
```

Ellos pueden probar la comunicación ejecutando en sus terminales:

* **Ver el estado de la zona en vivo**:
  ```bash
  ros2 topic echo /zone/occupant
  ```
  *(Verán `data: ''` cuando la zona esté libre, o `data: 'perry'` cuando esté cerrada/ordenando).*

* **Ver el estado del brazo**:
  ```bash
  ros2 topic echo /perry/state --once
  ```

* **Solicitar permiso para entrar a entregar**:
  ```bash
  ros2 service call /zone/request multirobot_interfaces/srv/RequestZone "{robot: 'ferb'}"
  ```
  *(Recibirán `granted: true, holder: 'ferb', lease_seconds: 60.0`).*

* **Liberar la zona tras dejar el cubo**:
  ```bash
  ros2 service call /zone/release multirobot_interfaces/srv/ReleaseZone "{robot: 'ferb', delivered: true, color: 'blue'}"
  ```
  *(Al recibir esto, Perry iniciará automáticamente el ciclo de ordenamiento si la zona está despejada).*

---

## 7. Cómo apagar todo al terminar el laboratorio

1. En la terminal de `audit_web.py`: Presiona `Ctrl + C`.
2. En la terminal de Docker:
   ```powershell
   docker compose -f compose_bridge.yaml down
   ```
3. Apaga la fuente de poder de los servos y desconecta los cables USB.

