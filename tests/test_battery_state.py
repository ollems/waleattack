"""Testes da máquina de estados da bateria com os pacotes REAIS capturados do X11.

Captura (cabo conectado, /dev/hidraw7 fa55):  03 55 40 03 64  a cada 2 s.
"""
from waleattack.battery import BatteryState
from waleattack import config


def ev(raw: bytes):
    e = config.parse_input_notification(raw)
    return e["status"], e["percent"]


CABLE_CHARGING = bytes.fromhex("0355400364")   # capturado: b3=3, b4=100 (placeholder)
CABLE_FULL = bytes.fromhex("0355400264")
DONGLE_2PCT = bytes([0x03, 0x55, 0x40, 0x01, 2])
DONGLE_37PCT = bytes([0x03, 0x55, 0x40, 0x01, 37])
DONGLE_DOCK = bytes([0x03, 0x55, 0x40, 0x03, 0x64])


def test_plug_cable_with_2pct_never_shows_100():
    b = BatteryState()
    b.on_report(*ev(DONGLE_2PCT), from_cable=False, now=0)
    assert b.level == 2 and not b.stale

    b.on_cable(True, now=10)
    for t in range(12, 40, 2):
        b.on_report(*ev(CABLE_CHARGING), from_cable=True, now=t)
    assert b.is_charging
    assert not b.is_full
    assert b.level == 2          # o placeholder 0x64 NÃO vira 100%


def test_unplug_cable_does_not_show_100_and_marks_stale():
    b = BatteryState()
    b.on_report(*ev(DONGLE_2PCT), from_cable=False, now=0)
    b.on_cable(True, now=1)
    b.on_report(*ev(CABLE_CHARGING), from_cable=True, now=2)

    b.on_cable(False, now=100)
    assert not b.is_charging
    assert b.level == 2
    assert b.waiting_reading      # nível antigo, aguardando leitura nova

    b.on_report(*ev(DONGLE_37PCT), from_cable=False, now=105)
    assert b.level == 37
    assert not b.waiting_reading
    assert b.mode == "discharging"


def test_cable_full_report():
    b = BatteryState()
    b.on_cable(True, now=0)
    b.on_report(*ev(CABLE_FULL), from_cable=True, now=1)
    assert b.is_full and b.level == 100
    b.on_cable(False, now=2)
    assert not b.is_full and not b.is_charging


def test_dock_charging_ignores_placeholder():
    b = BatteryState()
    b.on_report(*ev(DONGLE_37PCT), from_cable=False, now=0)
    b.on_report(*ev(DONGLE_DOCK), from_cable=False, now=1)
    assert b.is_dock and b.is_charging
    assert b.level == 37
    b.on_report(*ev(DONGLE_37PCT), from_cable=False, now=50)
    assert b.mode == "discharging" and b.level == 37


def test_restore_is_always_stale_and_rejects_garbage():
    b = BatteryState()
    b.restore(55, 123.0)
    assert b.level == 55 and b.waiting_reading
    b2 = BatteryState()
    b2.restore(None)
    assert b2.level is None and b2.waiting_reading


def test_late_dongle_packet_while_cable_present_is_ignored():
    b = BatteryState()
    b.on_cable(True, now=0)
    b.on_report(1, 100, from_cable=False, now=1)
    assert b.is_charging and b.level is None
