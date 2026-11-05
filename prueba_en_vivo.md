Ran check docs directory
Analyzed guia_laboratorio.md:L1-100
Created guia_laboratorio_laptop.md

Aquí tienes la **guía paso a paso para arrancar el proyecto desde cero en el laboratorio** utilizando tu laptop (Opción 1):

---

### Paso 0: Conexiones Físicas
1. **Cámara**: Conecta la webcam **Microsoft LifeCam Studio** a un puerto USB de tu laptop.
2. **Brazo Robótico**: Conecta el cable USB del **Pololu Mini Maestro 12** a tu laptop (se detectará en `COM5`).
3. **Alimentación Servos**: Enciende la fuente de poder de los servomotores (5V–6V).
   > *Sostén suavemente el brazo para evitar que caiga por peso muerto hasta que reciba el primer pulso.*
4. **Red Wi-Fi**: Conecta tu laptop a la **misma red Wi-Fi del laboratorio** donde estén conectadas las Raspberry Pi de Ferb y Phineas.

---

### Paso 1: Levantar el Panel Web y Hardware (Windows)
Abre tu primera terminal de **PowerShell** en la carpeta del proyecto y ejecuta:

```powershell
python perry/audit_web.py
```

* Abre tu navegador en: **`http://localhost:8000`**
* **Qué verificar en pantalla**:
  * Pestaña **Seguimiento**: Debe verse el video en vivo de la cámara Microsoft LifeCam y el recuadro verde de la zona de entrega.
  * Tarjeta **Perry**: Debe indicar `STOP` o `listo`.

---

### Paso 2: Levantar el Puente ROS 2 de la Flota (Docker)
Abre una **segunda terminal de PowerShell** en la misma carpeta y ejecuta:

```powershell
docker compose -f compose_bridge.yaml up -d
```

Para verificar que el puente enlazó con tu panel web:
```powershell
docker logs --tail 10 perry_ros_bridge
```
> Debes ver: `[perry_fleet_node]: Iniciando PerryRosBridge conectado a http://172.25.32.1:8000...`

---

### Paso 3: Habilitar la Zona para los Carros
1. Asegúrate de que **no haya cubos en la zona de entrega** y que el brazo esté en su posición de reposo (`vista`).
2. En el panel web (`http://localhost:8000`), presiona el botón:
   👉 **`Habilitar Zona (FREE)`**
3. El estado de Perry cambiará a **`FREE`** y el campo ocupante mostrará `ZONA LIBRE ("")`.

---

### Paso 4: Comandos para que tus compañeros prueben desde sus carros

Tus compañeros en sus Raspberry Pi solo deben tener configurado el dominio común:
```bash
export ROS_DOMAIN_ID=0
```

Y pueden ejecutar desde sus terminales:

1. **Ver si la zona está libre**:
   ```bash
   ros2 topic echo /zone/occupant
   ```
   *(Mostrará `data: ''` cuando la zona esté libre y lista para recibir entregas).*

2. **Pedir permiso para entrar (Solicitar Llave)**:
   ```bash
   ros2 service call /zone/request multirobot_interfaces/srv/RequestZone "{robot: 'ferb'}"
   ```
   *(Perry responderá `granted: true, holder: 'ferb', lease_seconds: 60.0`).*

3. **Avisar que dejaron el cubo (Liberar Zona)**:
   ```bash
   ros2 service call /zone/release multirobot_interfaces/srv/ReleaseZone "{robot: 'ferb', delivered: true, color: 'blue'}"
   ```
   *(Perry pasará a ordenar el cubo automáticamente en cuanto el carro despeje la zona).*

4. **Ver sus estados en tu pantalla**:
   * Cuando ellos publiquen en `/ferb/state` o `/phineas/state`, sus tarjetas en tu panel de `http://localhost:8000` se actualizarán automáticamente en vivo.

---

### Para detener el sistema al finalizar el laboratorio:
1. En la terminal de `audit_web.py`: presiona `Ctrl + C`.
2. En la terminal de Docker:
   ```powershell
   docker compose -f compose_bridge.yaml down
   ```
3. Apaga la fuente de los servos y desconecta los cables USB.

*(He dejado guardada esta referencia completa en el archivo [docs/guia_laboratorio_laptop.md](file:///c:/Users/crist/Documents/GitHub/Robot_Claw/docs/guia_laboratorio_laptop.md) para que la tengas disponible sin conexión en el laboratorio).*


http://10.76.16.34:8000/