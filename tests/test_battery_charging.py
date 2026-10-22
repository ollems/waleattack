import pytest
from waleattack import config


def test_battery_notification_0x40():
    # 0x03 0x55 0x40 <status> <percent>
    # Normal discharging: status 1, 68%
    data = bytes([0x03, 0x55, 0x40, 0x01, 68])
    ev = config.parse_input_notification(data)
    assert ev is not None
    assert ev["type"] == "battery"
    assert ev["percent"] == 68
    assert ev["status"] == 1

    # Charging via cable: status 1, 75%
    data_chg = bytes([0x03, 0x55, 0x40, 0x01, 75])
    ev_chg = config.parse_input_notification(data_chg)
    assert ev_chg is not None
    assert ev_chg["percent"] == 75
    assert ev_chg["status"] == 1

    # Cable unplug status (b3 == 2, but actual battery is 72%)
    data_unplug = bytes([0x03, 0x55, 0x40, 0x02, 72])
    ev_unplug = config.parse_input_notification(data_unplug)
    assert ev_unplug is not None
    assert ev_unplug["percent"] == 72
    assert ev_unplug["status"] == 2

    # Dock charging (status 3, 45%)
    data_dock = bytes([0x03, 0x55, 0x40, 0x03, 45])
    ev_dock = config.parse_input_notification(data_dock)
    assert ev_dock is not None
    assert ev_dock["percent"] == 45
    assert ev_dock["status"] == 3


def test_notification_0x60_does_not_override_battery():
    # 0x03 0x55 0x60 0x0a (10)
    # This is an RF link status, NOT battery percentage. It must never return 100% battery!
    data_rf = bytes([0x03, 0x55, 0x60, 0x0A, 0x00])
    ev = config.parse_input_notification(data_rf)
    assert ev is not None
    assert ev["type"] == "rf_status"
    assert ev["status"] == 10
    assert "percent" not in ev


def test_stage_and_polling_notifications():
    # DPI Stage change to stage 3
    data_stage = bytes([0x03, 0x55, 0x10, 0x03, 0x00])
    ev_stage = config.parse_input_notification(data_stage)
    assert ev_stage == {"type": "stage", "stage": 3}

    # Polling rate change to 1000Hz (code 4)
    data_poll = bytes([0x03, 0x55, 0x20, 0x04, 0x00])
    ev_poll = config.parse_input_notification(data_poll)
    assert ev_poll == {"type": "polling", "hz": 1000}
