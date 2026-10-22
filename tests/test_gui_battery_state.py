"""Integração GUI <-> máquina de estados (Tk real em xvfb, sem worker de hardware)."""
import tkinter as tk

import pytest

import waleattack.gui as gui
from waleattack.gui import WaleAttackApp


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(gui, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(gui, "PROFILES_FILE", tmp_path / "profiles.json")
    monkeypatch.setattr(WaleAttackApp, "_hidraw_monitor_worker", lambda self: None)
    monkeypatch.setattr(WaleAttackApp, "sync_from_hardware_async", lambda self: None)
    root = tk.Tk()
    root.withdraw()
    instance = WaleAttackApp(root)
    yield instance
    root.destroy()


def test_full_cycle_plug_unplug(app):
    # mouse em 2% no 2.4G
    app._handle_input_event({"type": "battery", "status": 1, "percent": 2}, False)
    assert app.battery_percent == 2

    # pluga o cabo: interface fa55 aparece e manda 03 55 40 03 64
    app._on_wired_changed(True)
    app._handle_input_event({"type": "battery", "status": 3, "percent": 100}, True)
    assert app.is_charging and not app.is_full
    assert app.battery_percent == 2
    app._draw_battery()
    texts = [app.battery_canvas.itemcget(i, "text") for i in app.battery_canvas.find_all()
             if app.battery_canvas.type(i) == "text"]
    assert not any("100%" in t for t in texts)
    assert any("Carregando" in t for t in texts)

    # retira o cabo
    app._on_wired_changed(False)
    assert not app.is_charging
    assert app.battery.waiting_reading
    texts = [app.battery_canvas.itemcget(i, "text") for i in app.battery_canvas.find_all()
             if app.battery_canvas.type(i) == "text"]
    assert not any("100%" in t for t in texts)
    assert any("Atualizando" in t for t in texts)

    # primeira leitura real do dongle
    app._handle_input_event({"type": "battery", "status": 1, "percent": 41}, False)
    assert app.battery_percent == 41 and not app.battery.waiting_reading


def test_placeholder_never_persisted(app, tmp_path):
    import json
    app._handle_input_event({"type": "battery", "status": 1, "percent": 9}, False)
    app._on_wired_changed(True)
    app._handle_input_event({"type": "battery", "status": 3, "percent": 100}, True)
    data = json.loads((tmp_path / "profiles.json").read_text())
    assert data["battery"]["level"] == 9
