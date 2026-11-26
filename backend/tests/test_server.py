"""Integration tests for FastAPI endpoints, Demo Mode, and WebSocket updates."""

from pathlib import Path

from fastapi.testclient import TestClient

from backend.presets_store import PresetsStore
from backend.server import create_app


def _make_client(tmp_path: Path) -> TestClient:
    store = PresetsStore(path=tmp_path / "config.json")
    app = create_app(store=store, enable_hotkeys=False)
    return TestClient(app)


def test_demo_mode_full_control_flow(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        # Initial state
        r = client.get("/api/state")
        assert r.status_code == 200
        snap = r.json()
        assert snap["ble_state"]["connected"] is False
        assert len(snap["saved_eq_presets"]) >= 4

        # Enable Demo Mode
        r = client.post("/api/demo", json={"enabled": True})
        assert r.status_code == 200
        ble = r.json()["ble_state"]
        assert ble["connected"] is True
        assert ble["demo_mode"] is True
        assert ble["firmware"] == "2.4.1"
        assert ble["device_name"] == "EDIFIER M60"

        # Volume control (0..16)
        r = client.post("/api/volume", json={"level": 13})
        assert r.status_code == 200
        assert r.json()["ble_state"]["volume"] == 13

        # Invalid volume rejected by Pydantic
        r = client.post("/api/volume", json={"level": 17})
        assert r.status_code == 422

        # Input source switching
        r = client.post("/api/input", json={"source": "bluetooth"})
        assert r.status_code == 200
        assert r.json()["ble_state"]["input_source"] == "bluetooth"
        assert r.json()["ble_state"]["a2dp_state"] == "streaming"

        # Playback (fire-and-forget AVRCP)
        r = client.post("/api/playback", json={"action": "next"})
        assert r.status_code == 200

        # EQ preset & Custom 6-band EQ
        r = client.post("/api/eq/preset", json={"preset": "game"})
        assert r.status_code == 200
        assert r.json()["ble_state"]["eq_preset"] == "game"

        # Updating a band auto-switches to customized
        r = client.post(
            "/api/eq/custom/band", json={"index": 0, "gain_db": 2.5}
        )
        assert r.status_code == 200
        ble = r.json()["ble_state"]
        assert ble["eq_preset"] == "customized"
        assert ble["custom_eq"]["bands"][0]["gain_db"] == 2.5

        # Smart light & prompt tone
        r = client.post(
            "/api/smart-light", json={"timer": "20s", "sensitivity": "low"}
        )
        assert r.status_code == 200
        assert r.json()["ble_state"]["smart_light_timer"] == "20s"
        assert r.json()["ble_state"]["smart_light_sensitivity"] == "low"

        r = client.post("/api/prompt-tone", json={"enabled": False})
        assert r.status_code == 200
        assert r.json()["ble_state"]["prompt_tone"] is False

        # LDAC
        r = client.post("/api/ldac", json={"mode": "48khz"})
        assert r.status_code == 200
        assert r.json()["ble_state"]["ldac_mode"] == "48khz"

        # Rename validation + execution
        r = client.post("/api/device/name", json={"name": "Desk M60"})
        assert r.status_code == 200
        assert r.json()["ble_state"]["device_name"] == "Desk M60"

        r = client.post("/api/device/name", json={"name": "A" * 36})
        assert r.status_code == 422

        # Save & delete local EQ profile
        r = client.post(
            "/api/eq/saved",
            json={
                "name": "My Curve",
                "gains_db": [1.0, 0.5, 0.0, 0.5, 1.0, 0.5],
                "freqs": [62, 250, 1000, 4000, 8000, 16000],
            },
        )
        assert r.status_code == 200
        pid = r.json()["preset"]["id"]

        r = client.delete(f"/api/eq/saved/{pid}")
        assert r.status_code == 200

        # USB status endpoint responds cleanly even without hardware attached
        r = client.get("/api/usb/status")
        assert r.status_code == 200
        assert "usb_vid_pid" in r.json()["usb_state"]

        # Raw frame sender
        r = client.post(
            "/api/raw",
            json={"hex": "AA EC 66 00 00", "expect_reply": True, "auto_checksum": True},
        )
        assert r.status_code == 200
        assert r.json()["sent_hex"] == "AA EC 66 00 00 FC"
        assert r.json()["reply_hex"].startswith("BB EC 66 00 02 10 0D")


def test_websocket_snapshot_and_broadcast(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        with client.websocket_connect("/ws") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "snapshot"
            assert "ble_state" in msg["data"]

            client.post("/api/demo", json={"enabled": True})
            seen_connected = False
            for _ in range(30):
                evt = ws.receive_json()
                if evt["type"] == "ble_state" and evt["data"].get("connected"):
                    seen_connected = True
                    break
            assert seen_connected


def test_app_icons_and_manifest_served(tmp_path: Path) -> None:
    with _make_client(tmp_path) as client:
        ico = client.get("/favicon.ico")
        assert ico.status_code == 200
        assert ico.headers["content-type"].startswith("image/x-icon")
        assert ico.content[:4] == b"\x00\x00\x01\x00"

        png = client.get("/icon.png")
        assert png.status_code == 200
        assert png.headers["content-type"].startswith("image/png")
        assert png.content[:4] == b"\x89PNG"

        manifest = client.get("/manifest.webmanifest")
        assert manifest.status_code == 200
        data = manifest.json()
        assert data["icons"][0]["src"] == "/icon.png"


def test_autostart_setting_endpoint(tmp_path: Path, monkeypatch) -> None:
    import backend.server as srv

    state = {"enabled": False}

    def fake_is_enabled() -> bool:
        return state["enabled"]

    def fake_set_autostart(enabled: bool) -> dict:
        state["enabled"] = bool(enabled)
        return {"enabled": state["enabled"], "command": "mock", "error": None}

    monkeypatch.setattr(srv, "is_autostart_enabled", fake_is_enabled)
    monkeypatch.setattr(srv, "set_autostart", fake_set_autostart)

    with _make_client(tmp_path) as client:
        snap = client.get("/api/state").json()
        assert snap["settings"]["autostart_enabled"] is False

        r = client.post("/api/settings/autostart", json={"enabled": True})
        assert r.status_code == 200
        assert r.json()["settings"]["autostart_enabled"] is True

        r = client.post("/api/settings/autostart", json={"enabled": False})
        assert r.status_code == 200
        assert r.json()["settings"]["autostart_enabled"] is False
