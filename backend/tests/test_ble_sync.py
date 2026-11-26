"""Tests for unsolicited BLE notifications and background speaker state sync."""

import pytest

from backend.ble_client import M60Controller
from backend.protocol import InputSource


@pytest.mark.asyncio
async def test_unsolicited_ble_notify_broadcasts_state() -> None:
    ctrl = M60Controller()
    ctrl.state.connected = True

    events: list[tuple[str, dict]] = []

    async def listener(event_type: str, payload: dict) -> None:
        events.append((event_type, payload))

    ctrl.add_listener(listener)

    # Simulate physical volume button press pushing BB EC 66 00 02 10 0B 2A (volume=11)
    ctrl._on_ble_notify(None, bytearray.fromhex("BB EC 66 00 02 10 0B 2A"))

    # Allow scheduled tasks to run
    import asyncio

    await asyncio.sleep(0)

    assert ctrl.state.volume == 11
    ble_events = [p for t, p in events if t == "ble_state"]
    assert ble_events
    assert ble_events[-1]["volume"] == 11


@pytest.mark.asyncio
async def test_sync_fast_state_detects_physical_speaker_changes() -> None:
    ctrl = M60Controller()
    await ctrl.set_demo_mode(True)

    events: list[tuple[str, dict]] = []

    async def listener(event_type: str, payload: dict) -> None:
        events.append((event_type, payload))

    ctrl.add_listener(listener)

    # Mutate simulator directly as if physical buttons on the speaker were pressed
    assert ctrl._sim is not None
    ctrl._sim.volume = 14
    ctrl._sim.input_source = InputSource.AUX

    changed = await ctrl.sync_fast_state()
    assert changed is True
    assert ctrl.state.volume == 14
    assert ctrl.state.input_source == "aux"

    ble_events = [p for t, p in events if t == "ble_state"]
    assert len(ble_events) == 1
    assert ble_events[0]["volume"] == 14
    assert ble_events[0]["input_source"] == "aux"

    # Second sync with no changes must not emit redundant ble_state
    events.clear()
    changed_again = await ctrl.sync_fast_state()
    assert changed_again is False
    assert [p for t, p in events if t == "ble_state"] == []
