"""Pruebas unitarias para ZoneArbiter y PerryState (Fase 2)."""
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from zone_arbiter import PerryState, ZoneArbiter  # noqa: E402


def test_initial_state():
    arb = ZoneArbiter()
    assert arb.state == PerryState.STOP
    assert arb.holder == ""
    assert arb.delivered_total == 0
    assert arb.sorted_total == 0
    assert arb.carrying is False
    assert arb.parked_ok is False
    assert arb.trigger_sort is False
    assert arb.occupant_msg == "perry"


def test_occupant_msg_in_all_states():
    arb = ZoneArbiter()

    # STOP -> "perry"
    arb.set_state(PerryState.STOP)
    assert arb.occupant_msg == "perry"

    # SCANNING -> "perry"
    arb.set_state(PerryState.SCANNING)
    assert arb.occupant_msg == "perry"

    # PICKING -> "perry"
    arb.set_state(PerryState.PICKING)
    assert arb.occupant_msg == "perry"

    # DROPPING -> "perry"
    arb.set_state(PerryState.DROPPING)
    assert arb.occupant_msg == "perry"

    # BLOCKED -> "perry"
    arb.set_state(PerryState.BLOCKED)
    assert arb.occupant_msg == "perry"

    # FREE pero parked_ok == False -> "perry" (REGLA CRÍTICA)
    arb.set_state(PerryState.FREE, parked_ok=False)
    assert arb.occupant_msg == "perry"

    # FREE y parked_ok == True -> ""
    arb.set_parked_ok(True)
    assert arb.occupant_msg == ""

    # RECEIVING -> nombre del carro
    arb.request_zone("ferb", now=100.0)
    assert arb.occupant_msg == "ferb"


def test_request_zone_granted_when_free_and_parked():
    arb = ZoneArbiter(lease_duration_s=60.0)
    arb.set_state(PerryState.FREE, parked_ok=True)

    granted, holder, remaining = arb.request_zone("ferb", now=100.0)
    assert granted is True
    assert holder == "ferb"
    assert remaining == 60.0
    assert arb.state == PerryState.RECEIVING
    assert arb.holder == "ferb"
    assert arb.lease_expires_at == 160.0
    assert arb.occupant_msg == "ferb"


def test_request_zone_denied_when_free_but_not_parked():
    arb = ZoneArbiter()
    arb.set_state(PerryState.FREE, parked_ok=False)

    granted, holder, remaining = arb.request_zone("ferb", now=100.0)
    assert granted is False
    assert holder == "perry"
    assert remaining == 0.0
    assert arb.state == PerryState.FREE
    assert arb.holder == ""


@pytest.mark.parametrize("state", [
    PerryState.STOP,
    PerryState.SCANNING,
    PerryState.PICKING,
    PerryState.DROPPING,
    PerryState.BLOCKED,
])
def test_request_zone_denied_in_busy_states(state):
    arb = ZoneArbiter()
    arb.set_state(state, parked_ok=True)

    granted, holder, remaining = arb.request_zone("phineas", now=100.0)
    assert granted is False
    assert holder == "perry"
    assert remaining == 0.0
    assert arb.state == state


def test_request_zone_denied_when_already_held_by_other_robot():
    arb = ZoneArbiter(lease_duration_s=60.0)
    arb.set_state(PerryState.FREE, parked_ok=True)
    arb.request_zone("ferb", now=100.0)

    # Phineas intenta pedir mientras Ferb tiene el turno
    granted, holder, remaining = arb.request_zone("phineas", now=110.0)
    assert granted is False
    assert holder == "ferb"
    assert remaining == 50.0  # 160 - 110
    assert arb.holder == "ferb"
    assert arb.state == PerryState.RECEIVING


def test_request_zone_renewal_by_same_robot():
    arb = ZoneArbiter(lease_duration_s=60.0)
    arb.set_state(PerryState.FREE, parked_ok=True)
    arb.request_zone("ferb", now=100.0)

    # Ferb renueva a los 30 segundos
    granted, holder, remaining = arb.request_zone("ferb", now=130.0)
    assert granted is True
    assert holder == "ferb"
    assert remaining == 60.0
    assert arb.lease_expires_at == 190.0  # 130 + 60


def test_release_zone_success_with_delivered():
    arb = ZoneArbiter()
    arb.set_state(PerryState.FREE, parked_ok=True)
    arb.request_zone("ferb", now=100.0)

    ok, total = arb.release_zone("ferb", delivered=True, color="blue", now=120.0)
    assert ok is True
    assert total == 1
    assert arb.delivered_total == 1
    assert arb.last_delivery_color == "blue"
    assert arb.holder == ""
    assert arb.state == PerryState.SCANNING
    assert arb.trigger_sort is True
    assert arb.occupant_msg == "perry"


def test_release_zone_success_without_delivered():
    arb = ZoneArbiter()
    arb.set_state(PerryState.FREE, parked_ok=True)
    arb.request_zone("phineas", now=100.0)

    ok, total = arb.release_zone("phineas", delivered=False, now=110.0)
    assert ok is True
    assert total == 0
    assert arb.delivered_total == 0
    assert arb.holder == ""
    assert arb.state == PerryState.SCANNING
    assert arb.trigger_sort is True


def test_release_zone_rejected_from_wrong_robot():
    arb = ZoneArbiter()
    arb.set_state(PerryState.FREE, parked_ok=True)
    arb.request_zone("ferb", now=100.0)

    # Phineas no puede liberar la zona si la tiene Ferb
    ok, total = arb.release_zone("phineas", delivered=True, now=115.0)
    assert ok is False
    assert total == 0
    assert arb.holder == "ferb"
    assert arb.state == PerryState.RECEIVING
    assert arb.trigger_sort is False


def test_release_zone_rejected_when_not_in_receiving():
    arb = ZoneArbiter()
    arb.set_state(PerryState.SCANNING)

    ok, total = arb.release_zone("ferb", delivered=True)
    assert ok is False
    assert total == 0


def test_tick_lease_expiration():
    arb = ZoneArbiter(lease_duration_s=60.0)
    arb.set_state(PerryState.FREE, parked_ok=True)
    arb.request_zone("ferb", now=100.0)  # vence en 160.0

    # Aún no vence
    assert arb.tick(now=150.0) is False
    assert arb.state == PerryState.RECEIVING
    assert arb.holder == "ferb"

    # Vence
    assert arb.tick(now=160.0) is True
    assert arb.state == PerryState.SCANNING
    assert arb.holder == ""
    assert arb.trigger_sort is True
    assert arb.occupant_msg == "perry"

    # Segundo tick ya no hace nada
    assert arb.tick(now=161.0) is False


def test_helpers_and_snapshot():
    arb = ZoneArbiter()
    arb.set_state(PerryState.PICKING, carrying=True, parked_ok=False)
    assert arb.carrying is True
    assert arb.state == PerryState.PICKING

    assert arb.increment_sorted() == 1
    assert arb.increment_sorted() == 2
    assert arb.sorted_total == 2

    arb.set_state(PerryState.SCANNING)
    arb._trigger_sort = True
    assert arb.consume_trigger_sort() is True
    assert arb.consume_trigger_sort() is False  # Ya fue consumido

    snap = arb.snapshot(now=200.0)
    assert snap["state"] == "SCANNING"
    assert snap["occupant"] == "perry"
    assert snap["sorted_total"] == 2
    assert snap["carrying"] is True
    assert snap["trigger_sort"] is False


def test_concurrent_access():
    """Prueba de concurrencia: múltiples hilos solicitando, liberando y chequeando tick."""
    arb = ZoneArbiter(lease_duration_s=0.01)
    arb.set_state(PerryState.FREE, parked_ok=True)
    errors = []

    def worker_ferb():
        for i in range(50):
            try:
                g, _, _ = arb.request_zone("ferb")
                if g:
                    arb.release_zone("ferb", delivered=True)
                arb.tick()
            except Exception as e:
                errors.append(e)

    def worker_phineas():
        for i in range(50):
            try:
                g, _, _ = arb.request_zone("phineas")
                if g:
                    arb.release_zone("phineas", delivered=True)
                arb.tick()
            except Exception as e:
                errors.append(e)

    def worker_arm():
        for i in range(50):
            try:
                if arb.consume_trigger_sort():
                    arb.set_state(PerryState.PICKING)
                    arb.set_state(PerryState.DROPPING, carrying=True)
                    arb.increment_sorted()
                    arb.set_state(PerryState.FREE, carrying=False, parked_ok=True)
                snap = arb.snapshot()
                assert "state" in snap
            except Exception as e:
                errors.append(e)

    threads = [
        threading.Thread(target=worker_ferb),
        threading.Thread(target=worker_phineas),
        threading.Thread(target=worker_arm),
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
