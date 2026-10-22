"""Decodificação e codificação dos reports 0x04, 0x05 e 0x06 (Hardware Wireless Gaming Mouse).

Estrutura dos reports de configuração:
* parser e construtor do report 0x04 (56 B, checksum 16-bit big-endian em [50:52])
* parser e construtor do report 0x05 (15 B, checksum 16-bit big-endian em [11:13])
* construtor do report 0x06 (9 B, polling rate)
* estágios padrão de fábrica: 800/1600/2400/3200/5000/22000 DPI,
  cores RGB #ff0000, #00ff00, #0000ff, #ffff00, #00ffff, #ff00ff
"""
from __future__ import annotations

from dataclasses import dataclass

from .dpi_table import DPI_CODE_TABLE

REPORT_ID = 0x04
REPORT_LEN = 0x38  # 56 bytes no fio (report_id + 55 bytes)
MAX_STAGES = 8

OFF_ANGLE_SNAP = 3      # +0x944 (0=off, 1=on)
OFF_RIPPLE_CONTROL = 4  # +0x940 (0=off, 1=on)
OFF_ENABLE_MASK = 5     # bit i = estágio i+1 habilitado
OFF_HIGH_MASK = 6       # bit i = estágio i+1 com pos > 220 (>11000 DPI)
OFF_HIGH_MASK_DUP = 7   # 0x4a21cd..0x4a21d2 grava o mesmo byte em [6] e [7]
OFF_CODES = 8           # 8 bytes: código de registrador de cada estágio
OFF_FLAGS = 16          # 8 bytes: flag de faixa alta na tabela (0 ou 1)
OFF_CURRENT = 24        # estágio atual (1-based)
OFF_COLORS = 25         # 8 * 3 bytes (R, G, B)
OFF_TAIL_CONST = 49     # sempre 0x02 (0x4a2378)
OFF_CHECKSUM_HI = 50    # (sum(report[3:50]) >> 8) & 0xFF
OFF_CHECKSUM_LO = 51    # sum(report[3:50]) & 0xFF

POLLING_BYTE_TO_HZ = {8: 125, 4: 250, 2: 500, 1: 1000}
POLLING_HZ_TO_BYTE = {v: k for k, v in POLLING_BYTE_TO_HZ.items()}

FACTORY_STAGES: tuple[tuple[int, bool, tuple[int, int, int]], ...] = (
    (800, True, (0xFF, 0x00, 0x00)),
    (1600, True, (0x00, 0xFF, 0x00)),
    (2400, True, (0x00, 0x00, 0xFF)),
    (3200, True, (0xFF, 0xFF, 0x00)),
    (5000, True, (0x00, 0xFF, 0xFF)),
    (22000, True, (0xFF, 0x00, 0xFF)),
    (50, False, (0xFF, 0x40, 0x00)),
    (50, False, (0xFF, 0xFF, 0xFF)),
)


def checksum16(report: bytes | bytearray) -> int:
    """Soma de 16 bits de report[3:50], gravada em big-endian em report[50:52] (0x4a2370)."""
    return sum(report[3:50]) & 0xFFFF


def _finalize_report04(buf: bytearray) -> bytes:
    buf[OFF_HIGH_MASK_DUP] = buf[OFF_HIGH_MASK]
    buf[OFF_TAIL_CONST] = 0x02
    ck = checksum16(buf)
    buf[OFF_CHECKSUM_HI] = (ck >> 8) & 0xFF
    buf[OFF_CHECKSUM_LO] = ck & 0xFF
    return bytes(buf)


def pos_to_dpi(pos: int) -> int:
    """Posição do slider (1..320) -> DPI. 1..200 = 50 DPI/passo; 201..320 = 100 DPI/passo."""
    return pos * 50 if pos <= 200 else 10000 + (pos - 200) * 100


def dpi_to_pos(dpi: int) -> int:
    """DPI (50..22000) -> posição do slider (1..320)."""
    if dpi < 50 or dpi > 22000:
        raise ValueError("DPI deve estar entre 50 e 22000")
    if dpi <= 10000:
        if dpi % 50 != 0:
            raise ValueError("Até 10000 DPI o passo é de 50 DPI")
        return dpi // 50
    if (dpi - 10000) % 100 != 0:
        raise ValueError("Acima de 10000 DPI o passo é de 100 DPI")
    pos = 200 + (dpi - 10000) // 100
    if pos > 300 and pos % 2 != 0:
        raise ValueError("Acima de 20000 DPI o passo no sensor é de 200 DPI")
    return pos


def code_to_pos(code: int, high_flag: bool, high_range: bool) -> int:
    """Replica o laço do parser (0x4994f0..0x49957c)."""
    rng = range(190, 220) if high_flag else range(0, 200)
    idx = next((i for i in rng if DPI_CODE_TABLE[i] == code), 0)
    if not high_range:
        return idx + 1
    return idx - 99 + 200 if idx < 200 else (idx - 149) * 2 + 200


def pos_to_code(pos: int) -> tuple[int, int, bool]:
    """Replica a codificação de escrita em 0x4a2130..0x4a225f.

    Retorna (code, high_flag, high_range).
    """
    if not 1 <= pos <= 320:
        raise ValueError(f"posição fora da faixa 1..320: {pos}")
    high_range = pos > 220
    if pos > 300:
        idx = 199 + (pos - 300) // 2
        high_flag = 1
    elif pos > 220:
        idx = pos - 101
        high_flag = 0
    else:
        idx = pos - 1
        high_flag = 1 if 201 <= pos <= 220 else 0
    return DPI_CODE_TABLE[idx], high_flag, high_range


def parse_hex_color(text: str) -> tuple[int, int, int]:
    s = text.strip().lstrip("#")
    if len(s) != 6:
        raise ValueError(f"cor hex inválida (use RRGGBB): {text}")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def snap_dpi(dpi: int) -> int:
    """Arredonda um valor arbitrário de DPI para o degrau válido mais próximo do PAW3311."""
    dpi = max(50, min(22000, int(dpi)))
    if dpi <= 10000:
        return max(50, int(round(dpi / 50.0)) * 50)
    if dpi <= 20000:
        return int(round(dpi / 100.0)) * 100
    return min(22000, int(round(dpi / 200.0)) * 200)


def update_stage_dpi(report: bytes, stage_number: int, dpi: int) -> bytes:
    """Retorna uma cópia do report 0x04 com o estágio `stage_number` (1..8) em `dpi`."""
    if len(report) != REPORT_LEN or report[0] != REPORT_ID:
        raise ValueError("report 0x04 inválido")
    if not 1 <= stage_number <= MAX_STAGES:
        raise ValueError("estágio deve ser 1..8")
    pos = dpi_to_pos(dpi)
    code, high_flag, high_range = pos_to_code(pos)

    buf = bytearray(report)
    idx = stage_number - 1
    buf[OFF_CODES + idx] = code
    buf[OFF_FLAGS + idx] = high_flag
    if high_range:
        buf[OFF_HIGH_MASK] |= 1 << idx
    else:
        buf[OFF_HIGH_MASK] &= ~(1 << idx)
    return _finalize_report04(buf)


def update_all_stages(
    report: bytes,
    stage_dpis: list[int],
    active_stage: int | None = None,
    stage_colors: list[tuple[int, int, int]] | None = None,
) -> bytes:
    """Atualiza múltiplos estágios, estágio ativo e cores em uma única operação no report 0x04."""
    buf = bytearray(report)
    for i, dpi in enumerate(stage_dpis[:MAX_STAGES]):
        pos = dpi_to_pos(snap_dpi(dpi))
        code, high_flag, high_range = pos_to_code(pos)
        buf[OFF_CODES + i] = code
        buf[OFF_FLAGS + i] = high_flag
        if high_range:
            buf[OFF_HIGH_MASK] |= 1 << i
        else:
            buf[OFF_HIGH_MASK] &= ~(1 << i)
    if active_stage is not None and 1 <= active_stage <= MAX_STAGES:
        buf[OFF_CURRENT] = active_stage
    if stage_colors is not None:
        for i, rgb in enumerate(stage_colors[:MAX_STAGES]):
            c = OFF_COLORS + 3 * i
            buf[c], buf[c + 1], buf[c + 2] = rgb[0] & 0xFF, rgb[1] & 0xFF, rgb[2] & 0xFF
    return _finalize_report04(buf)



def update_active_stage(report: bytes, stage_number: int) -> bytes:
    """Altera o estágio de DPI ativo (1..8)."""
    if len(report) != REPORT_LEN or report[0] != REPORT_ID:
        raise ValueError("report 0x04 inválido")
    if not 1 <= stage_number <= MAX_STAGES:
        raise ValueError("estágio deve ser 1..8")
    if not (report[OFF_ENABLE_MASK] & (1 << (stage_number - 1))):
        raise ValueError(f"estágio {stage_number} está desabilitado")
    buf = bytearray(report)
    buf[OFF_CURRENT] = stage_number
    return _finalize_report04(buf)


def update_stage_color(report: bytes, stage_number: int, rgb: tuple[int, int, int]) -> bytes:
    """Altera a cor RGB de um estágio de DPI (1..8)."""
    if len(report) != REPORT_LEN or report[0] != REPORT_ID:
        raise ValueError("report 0x04 inválido")
    if not 1 <= stage_number <= MAX_STAGES:
        raise ValueError("estágio deve ser 1..8")
    buf = bytearray(report)
    c = OFF_COLORS + 3 * (stage_number - 1)
    buf[c], buf[c + 1], buf[c + 2] = rgb[0] & 0xFF, rgb[1] & 0xFF, rgb[2] & 0xFF
    return _finalize_report04(buf)


def update_sensor_flags(report: bytes, *, angle_snap: bool | None = None,
                        ripple_control: bool | None = None) -> bytes:
    """Altera Angle Snap (byte 3) e/ou Ripple Control (byte 4) no report 0x04."""
    if len(report) != REPORT_LEN or report[0] != REPORT_ID:
        raise ValueError("report 0x04 inválido")
    buf = bytearray(report)
    if angle_snap is not None:
        buf[OFF_ANGLE_SNAP] = 1 if angle_snap else 0
    if ripple_control is not None:
        buf[OFF_RIPPLE_CONTROL] = 1 if ripple_control else 0
    return _finalize_report04(buf)


def reset_dpi_stages(report: bytes) -> bytes:
    """Restaura os estágios e cores padrão de fábrica do X11 (0x49f36c)."""
    if len(report) != REPORT_LEN or report[0] != REPORT_ID:
        raise ValueError("report 0x04 inválido")
    buf = bytearray(report)
    enable_mask = 0
    high_mask = 0
    for i, (dpi, enabled, color) in enumerate(FACTORY_STAGES):
        if enabled:
            enable_mask |= 1 << i
            pos = dpi_to_pos(dpi)
            code, high_flag, high_range = pos_to_code(pos)
            if high_range:
                high_mask |= 1 << i
        else:
            code, high_flag = 0, 0
        buf[OFF_CODES + i] = code
        buf[OFF_FLAGS + i] = high_flag
        c = OFF_COLORS + 3 * i
        buf[c], buf[c + 1], buf[c + 2] = color
    buf[OFF_ENABLE_MASK] = enable_mask
    buf[OFF_HIGH_MASK] = high_mask
    buf[OFF_CURRENT] = 2  # +0x934 = 1 (0-based) -> estágio 2 (1600 DPI) em 0x49f372
    return _finalize_report04(buf)


def parse_polling_report(report: bytes) -> int | None:
    """Extrai o polling rate em Hz do report 0x06 (0x4a3ab6)."""
    if len(report) < 5 or report[0] != 0x06:
        return None
    return POLLING_BYTE_TO_HZ.get(report[3])


def build_polling_report(hz: int) -> bytes:
    """Monta o report 0x06 (9 bytes) para `hz` in {125, 250, 500, 1000} (0x4a1f31..0x4a1f79)."""
    if hz not in POLLING_HZ_TO_BYTE:
        raise ValueError(f"polling rate inválido: {hz} (use 125, 250, 500 ou 1000)")
    b = POLLING_HZ_TO_BYTE[hz]
    return bytes([0x06, 0x09, 0x01, b, (~b) & 0xFF, 0x00, 0x00, 0x00, 0x00])


@dataclass
class AuxConfig:
    """Campos do report 0x05 decodificados por 0x4996e0."""

    raw: bytes
    checksum_ok: bool
    light_mode: int
    light_brightness: int
    light_speed: int
    light_color: tuple[int, int, int]
    sleep_time: int
    deep_sleep_time: int
    debounce_ms: int


def parse_aux_config(report: bytes) -> AuxConfig:
    if len(report) < 15 or report[0] != 0x05:
        raise ValueError("report 0x05 inválido")
    b = report[3:]
    light_mode = b[0] >> 4
    light_speed = 9 - (b[1] & 0x0F)
    light_brightness = b[2] & 0x0F
    deep_sleep = (b[2] >> 4) | (b[1] & 0xF0)
    color = (b[3], b[4], b[5])
    sleep_time = b[6]
    debounce_ms = b[7] * 2
    ck_expected = sum(report[3:11]) & 0xFFFF
    ck_actual = (report[11] << 8) | report[12]
    return AuxConfig(
        raw=report,
        checksum_ok=ck_expected == ck_actual,
        light_mode=light_mode,
        light_brightness=light_brightness,
        light_speed=light_speed,
        light_color=color,
        sleep_time=sleep_time,
        deep_sleep_time=deep_sleep,
        debounce_ms=debounce_ms,
    )


def update_aux_config(
    report: bytes,
    *,
    light_mode: int | None = None,
    light_brightness: int | None = None,
    light_speed: int | None = None,
    light_color: tuple[int, int, int] | None = None,
    sleep_time: int | None = None,
    deep_sleep_time: int | None = None,
    debounce_ms: int | None = None,
) -> bytes:
    """Reconstrói o report 0x05 (15 bytes) conforme 0x4a1e20..0x4a1f0d."""
    cur = parse_aux_config(report)
    mode = cur.light_mode if light_mode is None else light_mode
    bright = cur.light_brightness if light_brightness is None else light_brightness
    speed = cur.light_speed if light_speed is None else light_speed
    color = cur.light_color if light_color is None else light_color
    slp = cur.sleep_time if sleep_time is None else sleep_time
    dslp = cur.deep_sleep_time if deep_sleep_time is None else deep_sleep_time
    deb = cur.debounce_ms if debounce_ms is None else debounce_ms

    if not 0 <= mode <= 6:
        raise ValueError("light_mode deve ser 0..6")
    if not 1 <= bright <= 8:
        raise ValueError("light_brightness deve ser 1..8")
    if not 4 <= speed <= 8:
        raise ValueError("light_speed deve ser 4..8")
    if deb < 2 or deb > 30 or deb % 2 != 0:
        raise ValueError("debounce_ms deve ser par entre 2 e 30 ms")

    buf = bytearray(15)
    buf[0] = 0x05
    buf[1] = 0x0F
    buf[2] = 0x01
    buf[3] = (mode & 0x0F) << 4
    buf[4] = (dslp & 0xF0) | ((9 - speed) & 0x0F)
    low_nib = (bright & 0x0F) if mode in (1, 5) else 8
    buf[5] = ((dslp & 0x0F) << 4) | low_nib
    buf[6], buf[7], buf[8] = color[0] & 0xFF, color[1] & 0xFF, color[2] & 0xFF
    buf[9] = slp & 0xFF
    buf[10] = (deb // 2) & 0xFF
    ck = sum(buf[3:11]) & 0xFFFF
    buf[11] = (ck >> 8) & 0xFF
    buf[12] = ck & 0xFF
    return bytes(buf)


@dataclass
class DpiStage:
    number: int  # 1-based
    enabled: bool
    code: int
    dpi: int
    color: tuple[int, int, int]  # (R, G, B), validado pelos padrões em 0x49f3a2..0x49f562


@dataclass
class MainConfig:
    raw: bytes
    checksum_ok: bool
    current_stage: int
    angle_snap: bool
    ripple_control: bool
    stages: list[DpiStage]


def parse_main_config(report: bytes) -> MainConfig:
    if len(report) != REPORT_LEN or report[0] != REPORT_ID:
        raise ValueError("report 0x04 inválido")
    enable = report[OFF_ENABLE_MASK]
    high = report[OFF_HIGH_MASK]
    stages = []
    for i in range(MAX_STAGES):
        code = report[OFF_CODES + i]
        pos = code_to_pos(code, bool(report[OFF_FLAGS + i]), bool((high >> i) & 1))
        c = OFF_COLORS + 3 * i
        stages.append(
            DpiStage(
                number=i + 1,
                enabled=bool((enable >> i) & 1),
                code=code,
                dpi=pos_to_dpi(pos),
                color=(report[c], report[c + 1], report[c + 2]),
            )
        )
    ck_expected = checksum16(report)
    ck_actual = (report[OFF_CHECKSUM_HI] << 8) | report[OFF_CHECKSUM_LO]
    return MainConfig(
        raw=report,
        checksum_ok=ck_expected == ck_actual,
        current_stage=report[OFF_CURRENT],
        angle_snap=bool(report[OFF_ANGLE_SNAP]),
        ripple_control=bool(report[OFF_RIPPLE_CONTROL]),
        stages=stages,
    )


# ---------------------------------------------------------------------------
# Report 0x08: Mapeamento de botões (59 bytes = 0x3b, construtor em 0x4a26c0)
# Tabela de ações extraída de 0x4ec3b8..0x4ec8a8 e padrões de 0x4ec8f0.
# ---------------------------------------------------------------------------

BUTTON_ACTION_TRIPLETS: dict[int, tuple[int, int, int]] = {
    0x00: (0x01, 0x00, 0x00),  # Button Off
    0x01: (0x02, 0x00, 0x00),  # Left Click
    0x02: (0x03, 0x00, 0x00),  # Right Click
    0x03: (0x04, 0x00, 0x00),  # Middle Button
    0x04: (0x06, 0x00, 0x00),  # Forward
    0x05: (0x05, 0x00, 0x00),  # Backward
    0x06: (0x0D, 0x00, 0x00),  # DPI Cycle
    0x07: (0x0E, 0x00, 0x00),  # DPI +
    0x08: (0x0F, 0x00, 0x00),  # DPI -
    0x09: (0x07, 0x00, 0x00),  # Double Click
    0x0A: (0x08, 0x00, 0x00),  # Fire Button
    0x0B: (0x09, 0x00, 0x00),  # Scroll Up
    0x0C: (0x0A, 0x00, 0x00),  # Scroll Down
    0x0D: (0x0B, 0x00, 0x00),  # Scroll to Left
    0x0E: (0x0C, 0x00, 0x00),  # Scroll to Right
    0x16: (0x10, 0x00, 0x03),  # Easy Aim
    0x17: (0x29, 0x00, 0x03),  # LED Loop
    # Multimedia
    0x40: (0x15, 0x00, 0x00),  # Media Player
    0x41: (0x18, 0x00, 0x00),  # Play / Pause
    0x42: (0x19, 0x00, 0x00),  # Stop
    0x43: (0x16, 0x00, 0x00),  # Previous Track
    0x44: (0x17, 0x00, 0x00),  # Next Track
    0x45: (0x1B, 0x00, 0x00),  # Volume +
    0x46: (0x1C, 0x00, 0x00),  # Volume -
    0x47: (0x1A, 0x00, 0x00),  # Mute
    # Browser
    0x50: (0x25, 0x00, 0x00),  # Browser Home
    0x51: (0x11, 0x03, 0x12),  # Browser Favorites
    0x52: (0x20, 0x00, 0x00),  # Browser Forward
    0x53: (0x21, 0x00, 0x00),  # Browser Backward
    0x54: (0x22, 0x00, 0x00),  # Browser Stop
    0x55: (0x24, 0x00, 0x00),  # Browser Refresh
    0x56: (0x26, 0x00, 0x00),  # Browser Search
    0x57: (0x1E, 0x00, 0x00),  # Email
    0x58: (0x1D, 0x00, 0x00),  # Calculator
    0x59: (0x23, 0x00, 0x00),  # My Computer
    # Shortcut
    0x20: (0x11, 0x01, 0x1B),  # Cut
    0x21: (0x11, 0x01, 0x06),  # Copy
    0x22: (0x11, 0x01, 0x19),  # Paste
    0x23: (0x11, 0x01, 0x12),  # Open
    0x24: (0x11, 0x01, 0x16),  # Save
    0x25: (0x11, 0x01, 0x09),  # Find
    0x26: (0x11, 0x01, 0x1C),  # Redo
    0x28: (0x11, 0x01, 0x04),  # Select All
    0x29: (0x11, 0x01, 0x13),  # Print
    0x2A: (0x11, 0x04, 0x3D),  # Close Window
    0x2B: (0x11, 0x04, 0x2B),  # Swap Windows
    0x2C: (0x11, 0x08, 0x07),  # Show Desktop
    0x2D: (0x11, 0x08, 0x15),  # Run Command
    0x2E: (0x11, 0x08, 0x0F),  # Lock PC
    0x32: (0x11, 0x0A, 0x16),  # Screen Capture
}

BUTTON_ACTION_LABELS: dict[int, str] = {
    0x01: "Left Click",
    0x02: "Right Click",
    0x03: "Middle Button",
    0x04: "Forward",
    0x05: "Backward",
    0x09: "Double Click",
    0x0A: "Fire Button",
    0x16: "Easy Aim",
    0x0B: "Scroll Up",
    0x0C: "Scroll Down",
    0x00: "Button Off",
    0x06: "DPI Cycle",
    0x07: "DPI +",
    0x08: "DPI -",
    0x40: "Media Player",
    0x41: "Play / Pause",
    0x42: "Stop",
    0x43: "Previous Track",
    0x44: "Next Track",
    0x45: "Volume +",
    0x46: "Volume -",
    0x47: "Mute",
    0x50: "Browser Home",
    0x51: "Browser Favorites",
    0x52: "Browser Forward",
    0x53: "Browser Backward",
    0x54: "Browser Stop",
    0x55: "Browser Refresh",
    0x56: "Browser Search",
    0x57: "Email",
    0x58: "Calculator",
    0x59: "My Computer",
    0x20: "Cut",
    0x21: "Copy",
    0x22: "Paste",
    0x23: "Open",
    0x24: "Save",
    0x25: "Find",
    0x26: "Redo",
    0x28: "Select All",
    0x29: "Print",
    0x2A: "Close Window",
    0x2B: "Swap Windows",
    0x2C: "Show Desktop",
    0x2D: "Run Command",
    0x2E: "Lock PC",
    0x32: "Screen Capture",
}

# Índices dos 5 botões visíveis na GUI do X11 (ms_4_btn_key_1, 2, 3, 7, 8) dentro dos 18 slots
X11_BUTTON_SLOTS: tuple[int, int, int, int, int] = (0, 1, 2, 6, 7)

# 18 slots padrão de fábrica extraídos de 0x4ec8f0
FACTORY_BUTTON_SLOTS: tuple[int, ...] = (
    0x01, 0x02, 0x03, 0x00, 0x00, 0x06,
    0x04, 0x05, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x0B, 0x0C,
)

LIGHT_MODE_NAMES: dict[int, str] = {
    0: "LED Off",
    1: "Static",
    2: "Breathing",
    3: "Neon",
    4: "Color Breathing",
    5: "Static DPI",
    6: "Breathing DPI",
}


def build_factory_reset_report() -> bytes:
    """Report 0x0C (10 bytes) enviado em 0x4a1de8 ao restaurar padrões de fábrica."""
    return bytes([0x0C, 0x0A, 0x01, 0xFE, 0x01, 0xFE, 0x00, 0x00, 0x00, 0x00])


def encode_custom_key_action(mod_mask: int, hid_usage: int) -> int:
    """Codifica um atalho/macro de tecla (0x11, mod_mask, hid_usage) como inteiro >= 0x10000."""
    return 0x10000 | ((mod_mask & 0xFF) << 8) | (hid_usage & 0xFF)


def decode_action_triplet(act: int) -> tuple[int, int, int]:
    """Retorna a trinca (b0, b1, b2) para um código de ação padrão ou macro customizada."""
    if act >= 0x10000:
        mod = (act >> 8) & 0xFF
        usage = act & 0xFF
        return (0x11, mod, usage)
    return BUTTON_ACTION_TRIPLETS.get(act, (0x01, 0x00, 0x00))


def build_button_report(five_buttons: list[int] | tuple[int, ...]) -> bytes:
    """Constrói o report 0x08 (59 bytes) para os 5 botões principais do X11 (0x4a26c0).

    Em 0x4a26f7..0x4a27a4:
      buf[0] = 0x08, buf[1] = 0x3b, buf[2] = 0x01
      esi inicia em ebp-0xc8 (offset 4) e escreve:
        [esi-1] = b0 (offset 3 + i*3)
        [esi]   = b1 (offset 4 + i*3)
        [esi+1] = b2 (offset 5 + i*3)
      para os 18 slots (bytes 3..56), seguido do checksum big-endian nos bytes 57..58.
    """
    if len(five_buttons) != 5:
        raise ValueError("five_buttons deve conter exatamente 5 códigos de ação")
    if 0x01 not in five_buttons:
        raise ValueError('Pelo menos um botão deve ser "Left Click"!')

    slots = list(FACTORY_BUTTON_SLOTS)
    for btn_idx, slot_idx in enumerate(X11_BUTTON_SLOTS):
        slots[slot_idx] = five_buttons[btn_idx]

    buf = bytearray(0x3B)
    buf[0] = 0x08
    buf[1] = 0x3B
    buf[2] = 0x01
    for i, act in enumerate(slots):
        b0, b1, b2 = decode_action_triplet(act)
        off = 3 + i * 3
        buf[off] = b0
        buf[off + 1] = b1
        buf[off + 2] = b2
    ck = sum(buf[3:57]) & 0xFFFF
    buf[57] = (ck >> 8) & 0xFF
    buf[58] = ck & 0xFF
    return bytes(buf)


def parse_button_report(report: bytes) -> list[int] | None:
    """Decodifica os 5 botões do X11 a partir de um report 0x08 de 59 bytes."""
    if len(report) < 59 or report[0] != 0x08 or report[1] != 0x3B:
        return None
    rev = {triplet: code for code, triplet in BUTTON_ACTION_TRIPLETS.items()}
    result: list[int] = []
    default_five = [0x01, 0x02, 0x03, 0x04, 0x05]
    for idx, slot_idx in enumerate(X11_BUTTON_SLOTS):
        off = 3 + slot_idx * 3
        triplet = (report[off], report[off + 1], report[off + 2])
        if triplet in rev:
            result.append(rev[triplet])
        elif triplet[0] == 0x11:
            result.append(encode_custom_key_action(triplet[1], triplet[2]))
        else:
            result.append(default_five[idx])
    return result


def parse_input_notification(data: bytes) -> dict[str, int | bool | None] | None:
    """Decodifica notificações de Input Report 0x03 vindas de /dev/hidrawN (0x10001b37 / 0x4a1690)."""
    if len(data) < 5 or data[0] != 0x03 or data[1] != 0x55:
        return None
    kind = data[2]
    b3 = data[3]
    b4 = data[4]
    if kind == 0x10 and 1 <= b3 <= 8:
        return {"type": "stage", "stage": b3}
    if kind == 0x20 and 1 <= b3 <= 4:
        hz_map = {1: 125, 2: 250, 3: 500, 4: 1000}
        return {"type": "polling", "hz": hz_map.get(b3, 1000)}
    if kind == 0x40:
        clean_b4 = (b4 & 0x7F) if (b4 & 0x80) != 0 else b4
        pct = clean_b4 if 1 <= clean_b4 <= 100 else None
        return {
            "type": "battery",
            "status": b3,
            "percent": pct,
            "raw_b3": b3,
            "raw_b4": b4,
        }
    if kind == 0x60:
        return {"type": "rf_status", "status": b3}
    if kind == 0x50:
        return {"type": "wake", "awake": b3 == 0}
    if kind == 0x70:
        return {"type": "light_mode", "mode": (b3 >> 4) & 0x0F}
    return None


