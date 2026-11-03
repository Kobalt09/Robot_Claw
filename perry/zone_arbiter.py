"""Árbitro de zona y máquina de estados de Perry (Fase 2).

Implementación en Python puro (sin rclpy ni ROS 2) de la máquina de estados
y las reglas de exclusión mutua para el acceso a la zona de entrega entre Perry
y los robots recolectores (Ferb y Phineas).
"""
from enum import Enum
import threading
import time
from typing import Optional, Tuple, Dict, Any


class PerryState(str, Enum):
    """Estados del ciclo de operación y seguridad de Perry."""
    STOP = "STOP"            # Detenido / Inicial / Error
    SCANNING = "SCANNING"    # Escaneando la zona con la cámara cenital
    FREE = "FREE"            # Zona libre y brazo verificado en reposo
    RECEIVING = "RECEIVING"  # Zona cedida a un carro recolector para entrega
    PICKING = "PICKING"      # Agarrando un cubo o empujando un grupo
    DROPPING = "DROPPING"    # Transportando un cubo hacia el contenedor
    BLOCKED = "BLOCKED"      # Zona bloqueada por cubos inalcanzables / ignorados


class ZoneArbiter:
    """Árbitro thread-safe para la gestión de la zona compartida y estado de Perry."""

    def __init__(self, lease_duration_s: float = 60.0, initial_state: PerryState = PerryState.STOP):
        self._lock = threading.Lock()
        self._state: PerryState = initial_state
        self._holder: str = ""
        self._lease_expires_at: float = 0.0
        self._lease_duration_s: float = float(lease_duration_s)
        self._delivered_total: int = 0
        self._sorted_total: int = 0
        self._carrying: bool = False
        self._parked_ok: bool = False
        self._trigger_sort: bool = False
        self._last_delivery_color: str = ""

    # --- Propiedades thread-safe ---

    @property
    def state(self) -> PerryState:
        with self._lock:
            return self._state

    @property
    def holder(self) -> str:
        with self._lock:
            return self._holder

    @property
    def lease_expires_at(self) -> float:
        with self._lock:
            return self._lease_expires_at

    @property
    def lease_duration_s(self) -> float:
        return self._lease_duration_s

    @property
    def delivered_total(self) -> int:
        with self._lock:
            return self._delivered_total

    @property
    def sorted_total(self) -> int:
        with self._lock:
            return self._sorted_total

    @property
    def carrying(self) -> bool:
        with self._lock:
            return self._carrying

    @property
    def parked_ok(self) -> bool:
        with self._lock:
            return self._parked_ok

    @property
    def trigger_sort(self) -> bool:
        with self._lock:
            return self._trigger_sort

    @property
    def last_delivery_color(self) -> str:
        with self._lock:
            return self._last_delivery_color

    @property
    def occupant_msg(self) -> str:
        """Valor a publicar en el tópico ROS /zone/occupant.

        - Devuelve "" ÚNICAMENTE si state == FREE y parked_ok == True.
        - Devuelve el nombre del carro ("ferb" o "phineas") si state == RECEIVING.
        - En cualquier otro estado devuelve "perry" (zona ocupada / no disponible).
        """
        with self._lock:
            if self._state == PerryState.FREE and self._parked_ok:
                return ""
            if self._state == PerryState.RECEIVING:
                return self._holder
            return "perry"

    # --- Operaciones de lease de la zona ---

    def request_zone(self, robot: str, now: Optional[float] = None) -> Tuple[bool, str, float]:
        """Solicita o renueva el préstamo (lease) de la zona.

        Reglas:
        - Concede o renueva por lease_duration_s solo si:
          1) state == FREE y parked_ok == True (nueva concesión).
          2) state == RECEIVING y holder == robot (renovación por el mismo carro).
        - Al conceder, pasa el estado a RECEIVING y asigna holder.

        Retorna:
          (granted, current_holder, remaining_lease_s)
        """
        if now is None:
            now = time.time()

        with self._lock:
            # Caso 1: Renovación por el mismo robot poseedor
            if self._state == PerryState.RECEIVING and self._holder == robot:
                self._lease_expires_at = now + self._lease_duration_s
                return True, self._holder, self._lease_duration_s

            # Caso 2: Nueva concesión si está libre y verificado en reposo
            if self._state == PerryState.FREE and self._parked_ok:
                self._state = PerryState.RECEIVING
                self._holder = robot
                self._lease_expires_at = now + self._lease_duration_s
                return True, self._holder, self._lease_duration_s

            # Caso 3: Rechazado
            current_holder = self._holder if self._state == PerryState.RECEIVING else "perry"
            remaining = max(0.0, self._lease_expires_at - now) if self._state == PerryState.RECEIVING else 0.0
            return False, current_holder, remaining

    def release_zone(self, robot: str, delivered: bool, color: str = "", now: Optional[float] = None) -> Tuple[bool, int]:
        """Libera la zona tras la entrega o retirada del carro recolector.

        Reglas:
        - Solo puede liberar el carro que actualmente posee el lease (o si está vacante en RECEIVING).
        - Si delivered == True, incrementa delivered_total y guarda color.
        - Limpia holder, pasa a SCANNING y activa trigger_sort = True.

        Retorna:
          (ok, delivered_total)
        """
        if now is None:
            now = time.time()

        with self._lock:
            if self._state != PerryState.RECEIVING or (self._holder and self._holder != robot):
                return False, self._delivered_total

            if delivered:
                self._delivered_total += 1
                self._last_delivery_color = color

            self._holder = ""
            self._lease_expires_at = 0.0
            self._state = PerryState.SCANNING
            self._trigger_sort = True
            return True, self._delivered_total

    def tick(self, now: Optional[float] = None) -> bool:
        """Verifica periódicamente la expiración del lease de un carro.

        Si está en RECEIVING y el tiempo excedió lease_expires_at:
        - Cancela el lease, limpia el holder.
        - Pasa de RECEIVING a SCANNING y activa trigger_sort = True.

        Retorna True si ocurrió una expiración de lease.
        """
        if now is None:
            now = time.time()

        with self._lock:
            if self._state == PerryState.RECEIVING and now >= self._lease_expires_at:
                self._holder = ""
                self._lease_expires_at = 0.0
                self._state = PerryState.SCANNING
                self._trigger_sort = True
                return True
            return False

    # --- Métodos de sincronización con el ciclo del brazo ---

    def set_state(self, new_state: PerryState, carrying: Optional[bool] = None, parked_ok: Optional[bool] = None) -> None:
        """Actualiza el estado de Perry y flags asociados bajo lock."""
        with self._lock:
            self._state = new_state
            if carrying is not None:
                self._carrying = carrying
            if parked_ok is not None:
                self._parked_ok = parked_ok

    def set_parked_ok(self, ok: bool) -> None:
        """Actualiza el resultado de la comprobación física de reposo."""
        with self._lock:
            self._parked_ok = ok

    def set_carrying(self, carrying: bool) -> None:
        """Actualiza si la pinza sostiene un cubo."""
        with self._lock:
            self._carrying = carrying

    def increment_sorted(self) -> int:
        """Incrementa el contador de cubos clasificados con éxito por Perry."""
        with self._lock:
            self._sorted_total += 1
            return self._sorted_total

    def consume_trigger_sort(self) -> bool:
        """Lee y apaga atómicamente el flag trigger_sort."""
        with self._lock:
            triggered = self._trigger_sort
            self._trigger_sort = False
            return triggered

    def snapshot(self, now: Optional[float] = None) -> Dict[str, Any]:
        """Obtiene un diccionario consistente con el estado completo."""
        if now is None:
            now = time.time()
        with self._lock:
            rem = max(0.0, self._lease_expires_at - now) if self._state == PerryState.RECEIVING else 0.0
            if self._state == PerryState.FREE and self._parked_ok:
                occ = ""
            elif self._state == PerryState.RECEIVING:
                occ = self._holder
            else:
                occ = "perry"

            return {
                "state": self._state.value,
                "occupant": occ,
                "holder": self._holder,
                "lease_remaining_s": rem,
                "delivered_total": self._delivered_total,
                "sorted_total": self._sorted_total,
                "carrying": self._carrying,
                "parked_ok": self._parked_ok,
                "trigger_sort": self._trigger_sort,
                "last_delivery_color": self._last_delivery_color,
            }
