"""Interface gráfica WaleAttack (Linux e Windows) para mouses gaming (PAW3311/Telink/Beken).

Construída com Tkinter + Canvas vetorial customizado de alta performance.
"""
from __future__ import annotations

import json
import os
import queue
import select
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, simpledialog

from . import config, hidraw, protocol
from .battery import BatteryState

# Esquema de cores Oceanic Teal & Electric Cyan/Mint (Daylight #488889 / Night #111b1e)
BG_DAYLIGHT = "#488889"
BG_NIGHT = "#111b1e"
BG_MAIN = BG_DAYLIGHT
BG_CARD = "#162226"
BG_HEADER_OPEN = "#203338"
BG_HEADER_CLOSED = "#19282c"
BORDER_HEADER = "#36555c"
BORDER_CARD = "#294147"
BG_BTN = "#22363c"
BG_BTN_HOVER = "#2e4a52"
BORDER_BTN = "#3d616b"
TRACK_GRAY = "#2b4248"
FILL_RED = "#00e5c3"
BORDER_RED = "#00a896"
TEXT_WHITE = "#f0f7f7"
TEXT_MUTED = "#84a5ac"
CYAN_LED = "#00f5d4"
ORANGE_LOGO = "#00f5d4"
ORANGE_LIGHT = "#72efdd"

if sys.platform == "win32":
    CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "WaleAttack"
else:
    CONFIG_DIR = Path.home() / ".config" / "waleattack"
PROFILES_FILE = CONFIG_DIR / "profiles.json"

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    ASSETS_DIR = Path(sys._MEIPASS) / "waleattack" / "assets"
else:
    ASSETS_DIR = Path(__file__).resolve().parent / "assets"

LOGO_FILE = ASSETS_DIR / "logo_display.png"
LOGO_NIGHT_FILE = ASSETS_DIR / "logo_night.png"
APP_ICON_FILE = ASSETS_DIR / "app_icon.png"

# Mapeamento de teclas (Tkinter keysym -> USB HID Keyboard Usage ID) para Macros de Tecla
HID_KEY_USAGES: dict[str, tuple[int, str]] = {
    **{chr(ord("a") + i): (0x04 + i, chr(ord("A") + i)) for i in range(26)},
    "1": (0x1E, "1"), "2": (0x1F, "2"), "3": (0x20, "3"), "4": (0x21, "4"),
    "5": (0x22, "5"), "6": (0x23, "6"), "7": (0x24, "7"), "8": (0x25, "8"),
    "9": (0x26, "9"), "0": (0x27, "0"),
    "return": (0x28, "Enter"), "escape": (0x29, "Esc"), "backspace": (0x2A, "Backspace"),
    "tab": (0x2B, "Tab"), "space": (0x2C, "Space"),
    "minus": (0x2D, "-"), "equal": (0x2E, "="),
    "f1": (0x3A, "F1"), "f2": (0x3B, "F2"), "f3": (0x3C, "F3"), "f4": (0x3D, "F4"),
    "f5": (0x3E, "F5"), "f6": (0x3F, "F6"), "f7": (0x40, "F7"), "f8": (0x41, "F8"),
    "f9": (0x42, "F9"), "f10": (0x43, "F10"), "f11": (0x44, "F11"), "f12": (0x45, "F12"),
    "insert": (0x49, "Insert"), "home": (0x4A, "Home"), "prior": (0x4B, "PageUp"),
    "delete": (0x4C, "Delete"), "end": (0x4D, "End"), "next": (0x4E, "PageDown"),
    "right": (0x4F, "Right"), "left": (0x50, "Left"), "down": (0x51, "Down"), "up": (0x52, "Up"),
}
HID_USAGE_TO_NAME: dict[int, str] = {u: label for u, label in HID_KEY_USAGES.values()}


BUTTON_MENU_STRUCTURE: list[tuple[str, int | list[tuple[str, int]]]] = [
    ("Left Click", 0x01),
    ("Right Click", 0x02),
    ("Middle Button", 0x03),
    ("Forward", 0x04),
    ("Backward", 0x05),
    ("Double Click", 0x09),
    ("Fire Button", 0x0A),
    ("Easy Aim", 0x16),
    ("Scroll Up", 0x0B),
    ("Scroll Down", 0x0C),
    ("Button Off", 0x00),
    (
        "DPI",
        [
            ("DPI Cycle", 0x06),
            ("DPI +", 0x07),
            ("DPI -", 0x08),
        ],
    ),
    (
        "Multimedia",
        [
            ("Media Player", 0x40),
            ("Play / Pause", 0x41),
            ("Stop", 0x42),
            ("Previous Track", 0x43),
            ("Next Track", 0x44),
            ("Volume +", 0x45),
            ("Volume -", 0x46),
            ("Mute", 0x47),
        ],
    ),
    (
        "Browser",
        [
            ("Browser Home", 0x50),
            ("Browser Favorites", 0x51),
            ("Browser Forward", 0x52),
            ("Browser Backward", 0x53),
            ("Browser Stop", 0x54),
            ("Browser Refresh", 0x55),
            ("Browser Search", 0x56),
            ("Email", 0x57),
            ("Calculator", 0x58),
            ("My Computer", 0x59),
        ],
    ),
    (
        "Shortcut",
        [
            ("Cut", 0x20),
            ("Copy", 0x21),
            ("Paste", 0x22),
            ("Open", 0x23),
            ("Save", 0x24),
            ("Find", 0x25),
            ("Redo", 0x26),
            ("Select All", 0x28),
            ("Print", 0x29),
            ("Close Window", 0x2A),
            ("Swap Windows", 0x2B),
            ("Show Desktop", 0x2C),
            ("Run Command", 0x2D),
            ("Lock PC", 0x2E),
            ("Screen Capture", 0x32),
        ],
    ),
]


def default_profile_dict(name: str = "Profile1") -> dict:
    return {
        "name": name,
        "buttons": [0x01, 0x02, 0x03, 0x04, 0x05],
        "stage_dpis": [800, 1600, 2400, 3200, 5000, 22000],
        "stage_colors": [
            [255, 0, 0],
            [0, 255, 0],
            [0, 0, 255],
            [255, 255, 0],
            [0, 255, 255],
            [255, 0, 255],
        ],
        "active_stage": 2,
        "polling_hz": 1000,
        "light_mode": 4,
        "light_brightness": 8,
        "light_speed": 8,
        "light_color": [0, 255, 0],
        "sleep_time": 1,
        "deep_sleep_time": 10,
        "debounce_ms": 4,
        "ripple_control": True,
        "angle_snap": True,
    }


class CollapsibleCard(tk.Frame):
    """Painel retrátil idêntico aos blocos com cabeçalho e botão [-] do DuiLib."""

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        *,
        width: int = 262,
        expanded: bool = True,
        show_header: bool = True,
        on_toggle=None,
    ):
        super().__init__(parent, bg=BG_MAIN, width=width)
        self.card_width = width
        self.expanded = expanded
        self.on_toggle = on_toggle
        self._title = title

        if show_header:
            self.header = tk.Canvas(
                self,
                width=width,
                height=25,
                bg=BG_HEADER_OPEN if expanded else BG_HEADER_CLOSED,
                highlightthickness=1,
                highlightbackground=BORDER_HEADER,
                cursor="hand2",
            )
            self.header.pack(fill="x")
            self.header.bind("<Button-1>", self._toggle)
            self.header.bind("<Enter>", self._on_enter)
            self.header.bind("<Leave>", self._on_leave)
            self._draw_header(hover=False)
        else:
            self.header = None

        self.body = tk.Frame(
            self,
            bg=BG_CARD,
            width=width,
            highlightthickness=1,
            highlightbackground=BORDER_CARD,
        )
        if expanded:
            self.body.pack(fill="x")

    def _draw_header(self, hover: bool = False) -> None:
        if self.header is None:
            return
        self.header.delete("all")
        bg = BG_HEADER_OPEN if (self.expanded or hover) else BG_HEADER_CLOSED
        fg = TEXT_WHITE if (self.expanded or hover) else TEXT_MUTED
        self.header.configure(bg=bg)
        self.header.create_text(
            10,
            13,
            text=self._title,
            anchor="w",
            fill=fg,
            font=("Arial", 9),
        )
        # Ícone [-] à direita como na imagem original
        bx1, by1, bx2, by2 = self.card_width - 22, 10, self.card_width - 9, 16
        self.header.create_rectangle(bx1, by1, bx2, by2, outline="#8a8d90", fill="#25282b")
        self.header.create_line(bx1 + 2, (by1 + by2) // 2, bx2 - 2, (by1 + by2) // 2, fill="#d0d3d6")

    def _on_enter(self, _event=None) -> None:
        self._draw_header(hover=True)

    def _on_leave(self, _event=None) -> None:
        self._draw_header(hover=False)

    def _toggle(self, _event=None) -> None:
        self.set_expanded(not self.expanded)
        if self.on_toggle:
            self.on_toggle(self.expanded)

    def set_expanded(self, expanded: bool) -> None:
        self.expanded = expanded
        if expanded:
            self.body.pack(fill="x")
        else:
            self.body.pack_forget()
        self._draw_header(hover=False)


class DuiButton(tk.Canvas):
    """Botão escuro plano estilizado como skins/button_1_1.png e msg_btn_1.png."""

    def __init__(
        self,
        parent: tk.Widget,
        text: str,
        command=None,
        *,
        width: int = 220,
        height: int = 21,
        bg_normal: str = BG_BTN,
        bg_hover: str = BG_BTN_HOVER,
        border: str = BORDER_BTN,
        font=("Arial", 9),
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=bg_normal,
            highlightthickness=1,
            highlightbackground=border,
            cursor="hand2",
        )
        self._text = text
        self._command = command
        self._cw = width
        self._ch = height
        self._bg_normal = bg_normal
        self._bg_hover = bg_hover
        self._font = font
        self._hover = False
        self._draw()
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonRelease-1>", self._on_click)

    def _draw(self) -> None:
        self.delete("all")
        self.configure(bg=self._bg_hover if self._hover else self._bg_normal)
        self.create_text(
            self._cw // 2,
            self._ch // 2,
            text=self._text,
            fill=TEXT_WHITE,
            font=self._font,
        )

    def set_text(self, text: str) -> None:
        self._text = text
        self._draw()

    def _on_enter(self, _e=None) -> None:
        self._hover = True
        self._draw()

    def _on_leave(self, _e=None) -> None:
        self._hover = False
        self._draw()

    def _on_click(self, _e=None) -> None:
        if self._command:
            self._command()


class VerticalDpiSlider(tk.Canvas):
    """Slider vertical customizado com trilha cinza, preenchimento vermelho embaixo e thumb branco."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        min_val: int = 1,
        max_val: int = 320,
        value: int = 32,
        height: int = 132,
        width: int = 36,
        on_change=None,
        on_release=None,
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=BG_CARD,
            highlightthickness=0,
            cursor="hand2",
        )
        self.min_val = min_val
        self.max_val = max_val
        self.value = value
        self._cw = width
        self._ch = height
        self.on_change = on_change
        self.on_release = on_release
        self._pad_y = 9
        self._draw()
        self.bind("<Button-1>", self._on_mouse)
        self.bind("<B1-Motion>", self._on_mouse)
        self.bind("<ButtonRelease-1>", self._on_up)

    def _val_to_y(self, val: int) -> float:
        ratio = (val - self.min_val) / max(1, (self.max_val - self.min_val))
        ratio = max(0.0, min(1.0, ratio))
        usable = self._ch - 2 * self._pad_y
        return self._ch - self._pad_y - ratio * usable

    def _y_to_val(self, y: float) -> int:
        usable = self._ch - 2 * self._pad_y
        ratio = (self._ch - self._pad_y - y) / max(1, usable)
        ratio = max(0.0, min(1.0, ratio))
        return int(round(self.min_val + ratio * (self.max_val - self.min_val)))

    def _draw(self) -> None:
        self.delete("all")
        cx = self._cw // 2
        top_y = self._pad_y
        bot_y = self._ch - self._pad_y
        cur_y = self._val_to_y(self.value)

        # Trilha cinza
        self.create_rectangle(cx - 2, top_y, cx + 3, bot_y, fill=TRACK_GRAY, outline="")
        # Preenchimento vermelho inferior até o thumb
        if bot_y > cur_y:
            self.create_rectangle(cx - 2, cur_y, cx + 3, bot_y, fill=FILL_RED, outline="")
        # Thumb circular branco (12x12)
        r = 6
        self.create_oval(
            cx - r,
            cur_y - r,
            cx + r,
            cur_y + r,
            fill=TEXT_WHITE,
            outline="#c8cbce",
            width=1,
        )

    def set_value(self, val: int, notify: bool = False) -> None:
        self.value = max(self.min_val, min(self.max_val, int(val)))
        self._draw()
        if notify and self.on_change:
            self.on_change(self.value)

    def _on_mouse(self, event) -> None:
        new_val = self._y_to_val(event.y)
        if new_val != self.value:
            self.value = new_val
            self._draw()
            if self.on_change:
                self.on_change(self.value)

    def _on_up(self, _event) -> None:
        if self.on_release:
            self.on_release(self.value)


class HorizontalRedSlider(tk.Canvas):
    """Slider horizontal com trilha cinza, preenchimento vermelho à esquerda e thumb circular branco."""

    def __init__(
        self,
        parent: tk.Widget,
        *,
        min_val: int = 1,
        max_val: int = 60,
        value: int = 1,
        width: int = 190,
        height: int = 20,
        on_change=None,
        on_release=None,
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=BG_CARD,
            highlightthickness=0,
            cursor="hand2",
        )
        self.min_val = min_val
        self.max_val = max_val
        self.value = value
        self._cw = width
        self._ch = height
        self.on_change = on_change
        self.on_release = on_release
        self._pad_x = 8
        self._draw()
        self.bind("<Button-1>", self._on_mouse)
        self.bind("<B1-Motion>", self._on_mouse)
        self.bind("<ButtonRelease-1>", self._on_up)

    def _val_to_x(self, val: int) -> float:
        ratio = (val - self.min_val) / max(1, (self.max_val - self.min_val))
        ratio = max(0.0, min(1.0, ratio))
        usable = self._cw - 2 * self._pad_x
        return self._pad_x + ratio * usable

    def _x_to_val(self, x: float) -> int:
        usable = self._cw - 2 * self._pad_x
        ratio = (x - self._pad_x) / max(1, usable)
        ratio = max(0.0, min(1.0, ratio))
        return int(round(self.min_val + ratio * (self.max_val - self.min_val)))

    def _draw(self) -> None:
        self.delete("all")
        cy = self._ch // 2
        left_x = self._pad_x
        right_x = self._cw - self._pad_x
        cur_x = self._val_to_x(self.value)

        # Trilha cinza
        self.create_rectangle(left_x, cy - 2, right_x, cy + 3, fill=TRACK_GRAY, outline="")
        # Preenchimento vermelho à esquerda
        if cur_x > left_x:
            self.create_rectangle(left_x, cy - 2, cur_x, cy + 3, fill=FILL_RED, outline="")
        # Thumb circular branco
        r = 6
        self.create_oval(
            cur_x - r,
            cy - r,
            cur_x + r,
            cy + r,
            fill=TEXT_WHITE,
            outline="#c8cbce",
            width=1,
        )

    def set_value(self, val: int, notify: bool = False) -> None:
        self.value = max(self.min_val, min(self.max_val, int(val)))
        self._draw()
        if notify and self.on_change:
            self.on_change(self.value)

    def _on_mouse(self, event) -> None:
        new_val = self._x_to_val(event.x)
        if new_val != self.value:
            self.value = new_val
            self._draw()
            if self.on_change:
                self.on_change(self.value)

    def _on_up(self, _event) -> None:
        if self.on_release:
            self.on_release(self.value)


class RadioDot(tk.Canvas):
    """Ponto de seleção estilo DuiLib (preto quando inativo, vermelho vivo quando ativo)."""

    def __init__(
        self,
        parent: tk.Widget,
        text: str = "",
        *,
        selected: bool = False,
        command=None,
        width: int = 80,
        height: int = 20,
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=BG_CARD,
            highlightthickness=0,
            cursor="hand2",
        )
        self.text = text
        self.selected = selected
        self.command = command
        self._cw = width
        self._ch = height
        self._draw()
        self.bind("<Button-1>", self._on_click)

    def _draw(self) -> None:
        self.delete("all")
        cy = self._ch // 2
        cx = 10 if self.text else self._cw // 2
        r = 5
        fill = FILL_RED if self.selected else "#081214"
        outline = "#72efdd" if self.selected else "#36555c"
        self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill, outline=outline, width=1)
        if self.text:
            self.create_text(
                cx + 12,
                cy,
                text=self.text,
                anchor="w",
                fill=TEXT_WHITE,
                font=("Arial", 9),
            )

    def set_selected(self, selected: bool) -> None:
        self.selected = selected
        self._draw()

    def _on_click(self, _event=None) -> None:
        if self.command:
            self.command()


class WaleAttackApp:
    """Aplicação principal WaleAttack."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("WaleAttack - Gaming Mouse Manager")
        # Tkinter não é thread-safe: threads secundárias só enfileiram, a thread do Tk executa.
        self._ui_queue: queue.SimpleQueue = queue.SimpleQueue()
        self._main_thread = threading.current_thread()
        self.theme_mode: str = "daylight"
        self.custom_macros: list[dict] = []
        self.profiles: list[dict] = []
        self.active_profile_idx: int = 0
        self._load_profiles()

        self.bg_main = BG_DAYLIGHT if self.theme_mode == "daylight" else BG_NIGHT
        self.root.configure(bg=self.bg_main)
        self.root.geometry("1040x700")
        self.root.minsize(980, 650)

        self.raw04: bytes | None = None
        self.raw05: bytes | None = None
        self.raw06: bytes | None = None
        self._io_lock = threading.Lock()
        self._highlighted_callout: int | None = None

        # Estado em tempo real de bateria e carregamento (máquina de estados em battery.py).
        # O nível é do dispositivo (não do perfil) e só é atualizado por leituras REAIS.
        self.battery = BatteryState()
        saved = getattr(self, "_saved_battery", None) or {}
        self.battery.restore(saved.get("level"), saved.get("ts", 0.0))
        self._charge_anim_step: int = 0
        self._event_log_path = CONFIG_DIR / "hid_events.log"

        self._load_logo_images()
        self._build_ui()
        self._apply_theme()
        self._apply_profile_to_widgets(self.current_profile)

        # Worker em background assíncrono para monitoramento de nós hidraw e notificações
        self._worker_running: bool = True
        self._monitor_thread = threading.Thread(target=self._hidraw_monitor_worker, daemon=True)
        self._monitor_thread.start()

        # Sincroniza com o hardware em background logo ao abrir
        self.root.after(150, self.sync_from_hardware_async)
        # Animação contínua da barra quando estiver carregando
        self.root.after(180, self._tick_charging_animation)
        self.root.after(20, self._pump_ui_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    @property
    def current_profile(self) -> dict:
        return self.profiles[self.active_profile_idx]

    # Atalhos somente-leitura para o estado da bateria (usados pelo canvas central)
    @property
    def battery_percent(self) -> int | None:
        return self.battery.level

    @property
    def is_charging(self) -> bool:
        return self.battery.is_charging

    @property
    def is_full(self) -> bool:
        return self.battery.is_full

    @property
    def is_dock_charging(self) -> bool:
        return self.battery.is_dock

    @property
    def _is_wired(self) -> bool:
        return self.battery.cable_present

    def _battery_persist_dict(self) -> dict:
        bat = getattr(self, "battery", None)
        if bat is None:
            saved = getattr(self, "_saved_battery", None)
            return saved if isinstance(saved, dict) else {}
        return {"level": bat.level, "ts": bat.level_wall_ts}

    def _load_profiles(self) -> None:
        try:
            if PROFILES_FILE.exists():
                data = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("profiles"):
                    self.profiles = data["profiles"]
                    self.active_profile_idx = max(
                        0, min(len(self.profiles) - 1, int(data.get("active", 0)))
                    )
                    if data.get("theme_mode") in ("daylight", "night"):
                        self.theme_mode = data["theme_mode"]
                    if isinstance(data.get("macros"), list):
                        self.custom_macros = data["macros"]
                    if isinstance(data.get("battery"), dict):
                        self._saved_battery = data["battery"]
                    # Valores antigos por perfil podiam conter o placeholder 100% do cabo: descarta.
                    for prof in self.profiles:
                        prof.pop("battery_percent", None)
                    return
        except Exception:
            pass
        self.profiles = [default_profile_dict("Profile1")]
        self.active_profile_idx = 0
        self._save_profiles()

    def _save_profiles(self) -> None:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            PROFILES_FILE.write_text(
                json.dumps(
                    {
                        "active": self.active_profile_idx,
                        "theme_mode": self.theme_mode,
                        "macros": self.custom_macros,
                        "battery": self._battery_persist_dict(),
                        "profiles": self.profiles,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _load_logo_images(self) -> None:
        self._logo_day: tk.PhotoImage | None = None
        self._logo_night: tk.PhotoImage | None = None
        self._app_icon: tk.PhotoImage | None = None
        try:
            if APP_ICON_FILE.exists():
                self._app_icon = tk.PhotoImage(file=str(APP_ICON_FILE))
                self.root.iconphoto(True, self._app_icon)
        except Exception:
            pass
        try:
            if LOGO_FILE.exists():
                self._logo_day = tk.PhotoImage(file=str(LOGO_FILE))
            if LOGO_NIGHT_FILE.exists():
                self._logo_night = tk.PhotoImage(file=str(LOGO_NIGHT_FILE))
            else:
                self._logo_night = self._logo_day
        except Exception:
            pass

    def _toggle_theme(self) -> None:
        self.theme_mode = "night" if self.theme_mode == "daylight" else "daylight"
        self.bg_main = BG_DAYLIGHT if self.theme_mode == "daylight" else BG_NIGHT
        self._save_profiles()
        self._apply_theme()

    def _apply_theme(self) -> None:
        bg = self.bg_main
        self.root.configure(bg=bg)

        def walk(w: tk.Widget) -> None:
            try:
                cur_bg = str(w.cget("bg")).lower()
                if cur_bg in (BG_DAYLIGHT.lower(), BG_NIGHT.lower(), "#2c393b"):
                    w.configure(bg=bg)
            except Exception:
                pass
            for child in w.winfo_children():
                walk(child)

        walk(self.root)
        if hasattr(self, "status_label"):
            self.status_label.configure(bg=bg)
        if hasattr(self, "center_canvas"):
            self.center_canvas.configure(bg=bg)
            self._draw_center_canvas()

    # ------------------------------------------------------------------
    # Construção do Layout (3 colunas: Esquerda, Centro, Direita)
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        # Container principal de 3 colunas (alinhado ao topo exatamente como na referência)
        self.main_row = tk.Frame(self.root, bg=self.bg_main)
        self.main_row.pack(fill="both", expand=True, padx=24, pady=(12, 10))
        self.main_row.grid_columnconfigure(0, weight=0, minsize=262)
        self.main_row.grid_columnconfigure(1, weight=1, minsize=340)
        self.main_row.grid_columnconfigure(2, weight=0, minsize=274)
        self.main_row.grid_rowconfigure(0, weight=1)

        # Coluna Esquerda
        self.left_col = tk.Frame(self.main_row, bg=self.bg_main, width=262)
        self.left_col.grid(row=0, column=0, sticky="nw")
        self._build_left_column(self.left_col)

        # Coluna Central (Logo WALEATTACK + botão Daylight/Night + Mouse X11 top-down)
        self.center_col = tk.Frame(self.main_row, bg=self.bg_main)
        self.center_col.grid(row=0, column=1, sticky="nsew", padx=16)
        self._build_center_column(self.center_col)

        # Coluna Direita (com suporte a rolagem suave e barra fina lateral vermelha)
        self.right_outer = tk.Frame(self.main_row, bg=self.bg_main, width=274)
        self.right_outer.grid(row=0, column=2, sticky="ne")
        self._build_right_column(self.right_outer)

    def _build_left_column(self, parent: tk.Frame) -> None:
        # 1. Button Settings
        self.card_buttons = CollapsibleCard(parent, "Button Settings", width=262, expanded=True)
        self.card_buttons.pack(fill="x")

        btn_inner = tk.Frame(self.card_buttons.body, bg=BG_CARD, padx=10, pady=12)
        btn_inner.pack(fill="x")

        self.key_buttons: list[DuiButton] = []
        for i in range(5):
            row = tk.Frame(btn_inner, bg=BG_CARD)
            row.pack(fill="x", pady=4)

            badge = tk.Canvas(
                row,
                width=21,
                height=19,
                bg="#1d3036",
                highlightthickness=1,
                highlightbackground="#3d616b",
            )
            badge.pack(side="left", padx=(4, 8))
            badge.create_text(11, 10, text=str(i + 1), fill=TEXT_WHITE, font=("Arial", 8))

            b = DuiButton(
                row,
                config.BUTTON_ACTION_LABELS[0x01],
                command=lambda idx=i: self._open_button_menu(idx),
                width=198,
                height=21,
            )
            b.pack(side="left")
            b.bind("<Enter>", lambda _e, idx=i: self._highlight_mouse_callout(idx + 1, True), add="+")
            b.bind("<Leave>", lambda _e, idx=i: self._highlight_mouse_callout(idx + 1, False), add="+")
            self.key_buttons.append(b)

        # 2. Macro Manager
        macro_wrap = tk.Frame(parent, bg=BG_MAIN)
        macro_wrap.pack(fill="x", pady=(10, 0))
        self.macro_btn = DuiButton(
            macro_wrap,
            "Macro Manager",
            command=self._open_macro_dialog,
            width=262,
            height=25,
            bg_normal="#203338",
        )
        self.macro_btn.pack(fill="x")

        # 3. Profile
        profile_wrap = tk.Frame(parent, bg=BG_MAIN)
        profile_wrap.pack(fill="x", pady=(10, 0))
        self.card_profile = CollapsibleCard(profile_wrap, "Profile", width=262, expanded=True)
        self.card_profile.pack(fill="x")

        prof_body = tk.Frame(self.card_profile.body, bg=BG_CARD, padx=14, pady=8)
        prof_body.pack(fill="x")

        self.profile_canvas = tk.Canvas(
            prof_body,
            width=230,
            height=105,
            bg="#0b1316",
            highlightthickness=1,
            highlightbackground=BORDER_RED,
            cursor="hand2",
        )
        self.profile_canvas.pack(fill="x")
        self.profile_canvas.bind("<Button-1>", self._on_profile_list_click)

        # 5 botões de ícone abaixo da lista (+, lixeira, editar, importar, exportar)
        prof_btns = tk.Frame(prof_body, bg=BG_CARD)
        prof_btns.pack(fill="x", pady=(6, 2))
        icons = [
            ("add", self._profile_add),
            ("del", self._profile_delete),
            ("edit", self._profile_rename),
            ("imp", self._profile_import),
            ("exp", self._profile_export),
        ]
        for idx, (kind, cmd) in enumerate(icons):
            c = tk.Canvas(
                prof_btns,
                width=29,
                height=18,
                bg="#203338",
                highlightthickness=1,
                highlightbackground="#36555c",
                cursor="hand2",
            )
            c.pack(side="left", padx=(0 if idx == 0 else 20, 0))
            self._draw_profile_icon(c, kind)
            c.bind("<Enter>", lambda _e, w=c: w.configure(bg="#2e4a52"))
            c.bind("<Leave>", lambda _e, w=c: w.configure(bg="#203338"))
            c.bind("<ButtonRelease-1>", lambda _e, fn=cmd: fn())

        # 4. Power (Battery)
        power_wrap = tk.Frame(parent, bg=BG_MAIN)
        power_wrap.pack(fill="x", pady=(10, 0))
        self.card_power = CollapsibleCard(power_wrap, "Power", width=262, expanded=True)
        self.card_power.pack(fill="x")

        self.battery_canvas = tk.Canvas(
            self.card_power.body,
            width=260,
            height=108,
            bg=BG_CARD,
            highlightthickness=0,
            cursor="hand2",
        )
        self.battery_canvas.pack(fill="x")
        self.battery_canvas.bind("<Button-1>", lambda _e: self.sync_from_hardware_async())

        # 5. Reset Profile
        reset_wrap = tk.Frame(parent, bg=BG_MAIN)
        reset_wrap.pack(fill="x", pady=(10, 0))
        self.reset_btn = DuiButton(
            reset_wrap,
            "Reset Profile",
            command=self._reset_profile_action,
            width=160,
            height=26,
            bg_normal="#203338",
        )
        self.reset_btn.pack()

    def _draw_profile_icon(self, c: tk.Canvas, kind: str) -> None:
        col = "#9ec4cb"
        if kind == "add":
            c.create_line(14, 4, 14, 14, fill=col, width=1)
            c.create_line(9, 9, 19, 9, fill=col, width=1)
        elif kind == "del":
            c.create_line(9, 5, 20, 5, fill=col)
            c.create_rectangle(11, 5, 18, 14, outline=col)
            c.create_line(13, 4, 16, 4, fill=col)
        elif kind == "edit":
            c.create_line(10, 14, 19, 5, fill=col, width=2)
            c.create_polygon(9, 15, 12, 14, 10, 12, fill=col)
        elif kind == "imp":
            c.create_rectangle(9, 6, 19, 14, outline=col)
            c.create_line(14, 3, 14, 11, fill=col)
            c.create_line(11, 9, 14, 12, fill=col)
            c.create_line(17, 9, 14, 12, fill=col)
        elif kind == "exp":
            c.create_rectangle(9, 6, 19, 14, outline=col)
            c.create_line(14, 12, 14, 4, fill=col)
            c.create_line(11, 7, 14, 4, fill=col)
            c.create_line(17, 7, 14, 4, fill=col)

    # ------------------------------------------------------------------
    # Coluna Central: Logo WALEATTACK + Ilustração Vetorial do Mouse X11
    # ------------------------------------------------------------------
    def _build_center_column(self, parent: tk.Frame) -> None:
        self.center_canvas = tk.Canvas(
            parent,
            width=340,
            height=635,
            bg=BG_MAIN,
            highlightthickness=0,
        )
        self.center_canvas.pack(fill="both", expand=True)
        self.center_canvas.bind("<Configure>", lambda _e: self._draw_center_canvas())
        self.center_canvas.bind("<Button-1>", self._on_center_canvas_click)

        self.status_label = tk.Label(
            parent,
            text="Searching X11 receiver (1d57:fa60)...",
            bg=BG_MAIN,
            fg="#a8d8dc",
            font=("Arial", 8),
            cursor="hand2",
        )
        self.status_label.pack(pady=(0, 2))
        self.status_label.bind("<Button-1>", lambda _e: self.sync_from_hardware_async())

    def _draw_center_canvas(self) -> None:
        c = self.center_canvas
        c.delete("all")
        w = max(340, c.winfo_width())
        cx = w // 2

        # 1. Cabeçalho / Logo Oficial WaleAttack (PNG com transparência)
        is_day = getattr(self, "theme_mode", "daylight") == "daylight"
        logo = self._logo_day if is_day else self._logo_night
        if logo:
            c.create_image(cx, 30, image=logo, anchor="center")
        else:
            c.create_text(
                cx,
                30,
                text="WALEATTACK",
                fill="#00f5d4",
                font=("Arial", 16, "bold", "italic"),
            )

        # 1b. Botão de alternância Daylight (#488889) / Night Mode no topo central
        tb_x1, tb_y1, tb_x2, tb_y2 = cx - 86, 58, cx + 86, 84
        self._theme_btn_bbox = (tb_x1, tb_y1, tb_x2, tb_y2)
        is_day = getattr(self, "theme_mode", "daylight") == "daylight"
        # Moldura externa do seletor
        c.create_rectangle(
            tb_x1,
            tb_y1,
            tb_x2,
            tb_y2,
            fill="#142226",
            outline="#66989b" if is_day else "#36555c",
            width=1,
        )
        # Aba Daylight (esquerda)
        c.create_rectangle(
            tb_x1 + 2,
            tb_y1 + 2,
            cx - 1,
            tb_y2 - 2,
            fill="#2b5d63" if is_day else "#19282c",
            outline="#00f5d4" if is_day else "",
        )
        c.create_text(
            (tb_x1 + cx) // 2,
            (tb_y1 + tb_y2) // 2,
            text="☀ Daylight",
            fill=TEXT_WHITE if is_day else TEXT_MUTED,
            font=("Arial", 8, "bold" if is_day else "normal"),
        )
        # Aba Night (direita)
        c.create_rectangle(
            cx + 1,
            tb_y1 + 2,
            tb_x2 - 2,
            tb_y2 - 2,
            fill="#243c42" if not is_day else "#19282c",
            outline=ORANGE_LIGHT if not is_day else "",
        )
        c.create_text(
            (cx + tb_x2) // 2,
            (tb_y1 + tb_y2) // 2,
            text="🌙 Night",
            fill=TEXT_WHITE if not is_day else TEXT_MUTED,
            font=("Arial", 8, "bold" if not is_day else "normal"),
        )

        # 2. Ilustração Top-Down do Mouse WaleAttack
        mx = cx
        my = 148  # topo do mouse
        mw = 194  # largura máxima
        mh = 385  # altura do corpo

        # Sombra externa sutil adaptada ao modo Daylight / Night
        shadow_col = "#36696a" if is_day else "#0b1214"
        c.create_oval(mx - mw // 2 - 3, my + 6, mx + mw // 2 + 3, my + mh + 6, fill=shadow_col, outline="")

        # Contorno principal da carcaça simétrica do X11 (polígono suavizado)
        shell_pts = [
            mx - 12, my,
            mx - 58, my + 12,
            mx - 88, my + 32,
            mx - 90, my + 110,
            mx - 84, my + 195,
            mx - 95, my + 275,
            mx - 82, my + 342,
            mx - 45, my + 378,
            mx, my + mh,
            mx + 45, my + 378,
            mx + 82, my + 342,
            mx + 95, my + 275,
            mx + 84, my + 195,
            mx + 90, my + 110,
            mx + 88, my + 32,
            mx + 58, my + 12,
            mx + 12, my,
        ]
        c.create_polygon(
            shell_pts,
            fill="#f2f4f5",
            outline="#1c1f21",
            width=2,
            smooth=True,
        )

        # Brilho interno suave na traseira do mouse (efeito 3D perolado)
        inner_pts = [
            mx - 68, my + 175,
            mx - 78, my + 268,
            mx - 62, my + 335,
            mx, my + 368,
            mx + 62, my + 335,
            mx + 78, my + 268,
            mx + 68, my + 175,
        ]
        c.create_polygon(inner_pts, fill="#fafbfc", outline="", smooth=True)

        # Botões laterais esquerdos (Forward = 4, Backward = 5)
        # Botão lateral frontal (4)
        c.create_polygon(
            mx - 89, my + 124,
            mx - 95, my + 130,
            mx - 95, my + 168,
            mx - 87, my + 174,
            fill="#e6eaec",
            outline="#45494c",
            width=1.5,
        )
        # Botão lateral traseiro (5)
        c.create_polygon(
            mx - 87, my + 182,
            mx - 94, my + 188,
            mx - 93, my + 230,
            mx - 85, my + 236,
            fill="#e6eaec",
            outline="#45494c",
            width=1.5,
        )

        # Linhas de divisão das placas dos botões principais (Esquerdo e Direito)
        # Fenda frontal central
        c.create_rectangle(mx - 13, my, mx + 13, my + 46, fill="#b8bec2", outline="#5a5e62")
        # Divisão vertical abaixo do scroll até a costura transversal
        c.create_line(mx, my + 102, mx, my + 172, fill="#222528", width=1.8)
        # Costura transversal das placas dos botões principais
        c.create_line(
            mx - 83, my + 50,
            mx - 82, my + 165,
            mx - 74, my + 172,
            mx, my + 172,
            fill="#222528",
            width=1.6,
            smooth=False,
        )
        c.create_line(
            mx, my + 172,
            mx + 74, my + 172,
            mx + 82, my + 165,
            mx + 83, my + 50,
            fill="#222528",
            width=1.6,
            smooth=False,
        )
        # Vincos laterais superiores das placas
        c.create_line(mx - 78, my + 24, mx - 83, my + 55, fill="#35393c", width=1.5)
        c.create_line(mx + 78, my + 24, mx + 83, my + 55, fill="#35393c", width=1.5)

        # Scroll Wheel central (botão 3)
        sw_x1, sw_y1, sw_x2, sw_y2 = mx - 13, my + 44, mx + 13, my + 102
        c.create_rectangle(sw_x1, sw_y1, sw_x2, sw_y2, fill="#1b1d1f", outline="#0c0d0e", width=2)
        # Frisos prateados laterais do scroll
        c.create_line(sw_x1 + 3, sw_y1 + 3, sw_x1 + 3, sw_y2 - 3, fill="#d8dde0", width=2)
        c.create_line(sw_x2 - 3, sw_y1 + 3, sw_x2 - 3, sw_y2 - 3, fill="#d8dde0", width=2)
        # Textura horizontal da borracha do scroll
        for sy in range(sw_y1 + 8, sw_y2 - 6, 5):
            c.create_line(sw_x1 + 6, sy, sw_x2 - 6, sy, fill="#373b3e", width=1.5)

        # LED indicador central (ciano ou verde-esmeralda se carregando)
        c.create_rectangle(
            mx - 6,
            my + 181,
            mx + 6,
            my + 185,
            fill="#10b981" if self.is_charging else CYAN_LED,
            outline="",
        )

        # 3. Callouts numerados (1..5) no novo esquema Teal/Cyan Elétrico
        self._callout_coords: dict[int, tuple[int, int]] = {
            1: (mx - 42, my + 78),
            3: (mx, my + 72),
            2: (mx + 46, my + 78),
            4: (mx - 88, my + 146),
            5: (mx - 88, my + 202),
        }
        for num, (bx, by) in self._callout_coords.items():
            is_hi = self._highlighted_callout == num
            r = 13 if is_hi else 11
            c.create_oval(
                bx - r,
                by - r,
                bx + r,
                by + r,
                fill="#00b4d8" if is_hi else "#0a9396",
                outline=TEXT_WHITE if is_hi else "#00f5d4",
                width=2 if is_hi else 1.5,
                tags=(f"callout_{num}",),
            )
            c.create_text(
                bx,
                by,
                text=str(num),
                fill=TEXT_WHITE,
                font=("Arial", 9, "bold"),
                tags=(f"callout_{num}",),
            )

        # 4. Indicador de conexão (Cabo USB vs Wireless 2.4G)
        wy = my + mh + 26
        self._wireless_icon_pos = (mx, wy)
        if getattr(self, "_is_wired", False):
            # Conector de Cabo USB no rodapé
            c.create_rectangle(mx - 8, wy - 4, mx + 8, wy + 6, fill="#203338", outline="#00f5d4", width=1.5)
            status_txt = "⚡ CABO USB (CARGA COMPLETA)" if getattr(self, "is_full", False) else "⚡ CONECTADO VIA CABO USB (CARREGANDO)"
            c.create_text(mx, wy + 24, text=status_txt, fill="#72efdd", font=("Arial", 8, "bold"))
        else:
            # Ícone Wireless ((o)) abaixo do mouse (exatamente como na referência)
            c.create_oval(mx - 2, wy - 2, mx + 2, wy + 2, fill="#e5ebed", outline="")
            c.create_line(mx, wy + 2, mx, wy + 9, fill="#e5ebed", width=1.5)
            for rad in (5, 8, 11):
                c.create_arc(
                    mx - rad,
                    wy - rad,
                    mx + rad,
                    wy + rad,
                    start=135,
                    extent=90,
                    style="arc",
                    outline="#e5ebed",
                    width=1.4,
                )
                c.create_arc(
                    mx - rad,
                    wy - rad,
                    mx + rad,
                    wy + rad,
                    start=-45,
                    extent=90,
                    style="arc",
                    outline="#e5ebed",
                    width=1.4,
                )
            c.create_text(mx, wy + 22, text="RECEPTOR 2.4G SEM FIO", fill=TEXT_MUTED, font=("Arial", 7, "bold"))

    def _highlight_mouse_callout(self, num: int, active: bool) -> None:
        self._highlighted_callout = num if active else None
        self._draw_center_canvas()

    def _on_center_canvas_click(self, event) -> None:
        tb = getattr(self, "_theme_btn_bbox", None)
        if tb and tb[0] <= event.x <= tb[2] and tb[1] <= event.y <= tb[3]:
            mid_x = (tb[0] + tb[2]) // 2
            target = "daylight" if event.x < mid_x else "night"
            if self.theme_mode == target:
                self._toggle_theme()
            else:
                self.theme_mode = target
                self.bg_main = BG_DAYLIGHT if target == "daylight" else BG_NIGHT
                self._save_profiles()
                self._apply_theme()
            return
        for num, (bx, by) in getattr(self, "_callout_coords", {}).items():
            if (event.x - bx) ** 2 + (event.y - by) ** 2 <= 14**2:
                self._open_button_menu(num - 1)
                return
        wx, wy = getattr(self, "_wireless_icon_pos", (0, 0))
        if (event.x - wx) ** 2 + (event.y - wy) ** 2 <= 18**2:
            self.sync_from_hardware_async()

    # ------------------------------------------------------------------
    # Coluna Direita: Painéis retráteis (DPI, Light, Polling, Power, etc.)
    # ------------------------------------------------------------------
    def _build_right_column(self, parent: tk.Frame) -> None:
        # Canvas com scrollbar fina vermelha lateral (igual à barra direita da screenshot)
        self.right_canvas = tk.Canvas(
            parent,
            width=262,
            height=668,
            bg=BG_MAIN,
            highlightthickness=0,
        )
        self.right_scroll = tk.Canvas(
            parent,
            width=5,
            height=668,
            bg="#232c2e",
            highlightthickness=0,
        )
        self.right_canvas.pack(side="left", fill="both", expand=True)
        self.right_scroll.pack(side="right", fill="y", padx=(4, 0))

        self.right_inner = tk.Frame(self.right_canvas, bg=BG_MAIN, width=262)
        self._right_win = self.right_canvas.create_window((0, 0), window=self.right_inner, anchor="nw")

        self.right_inner.bind("<Configure>", self._update_right_scroll)
        self.right_canvas.bind("<Configure>", self._update_right_scroll)
        # Suporte à roda do mouse na coluna direita
        self.root.bind_all("<Button-4>", self._on_mousewheel_up)
        self.root.bind_all("<Button-5>", self._on_mousewheel_down)
        self.root.bind_all("<MouseWheel>", self._on_mousewheel_win)

        # 1. DPI Settings (expandido por padrão, igual à referência)
        self.card_dpi = CollapsibleCard(
            self.right_inner,
            "DPI Settings",
            width=262,
            expanded=True,
            on_toggle=lambda _: self._update_right_scroll(),
        )
        self.card_dpi.pack(fill="x")
        self._build_dpi_card(self.card_dpi.body)

        # 2. Light Settings (recolhido na referência; abre ao clicar)
        light_wrap = tk.Frame(self.right_inner, bg=BG_MAIN)
        light_wrap.pack(fill="x", pady=(6, 0))
        self.card_light = CollapsibleCard(
            light_wrap,
            "Light Settings",
            width=262,
            expanded=False,
            on_toggle=lambda _: self._update_right_scroll(),
        )
        self.card_light.pack(fill="x")
        self._build_light_card(self.card_light.body)

        # 3. Polling Rate Settings (recolhido na referência; abre ao clicar)
        poll_wrap = tk.Frame(self.right_inner, bg=BG_MAIN)
        poll_wrap.pack(fill="x", pady=(6, 0))
        self.card_polling = CollapsibleCard(
            poll_wrap,
            "Polling Rate Settings",
            width=262,
            expanded=False,
            on_toggle=lambda _: self._update_right_scroll(),
        )
        self.card_polling.pack(fill="x")
        self._build_polling_card(self.card_polling.body)

        # 4. Mouse Attribute (recolhido na referência; abre ao clicar)
        attr_wrap = tk.Frame(self.right_inner, bg=BG_MAIN)
        attr_wrap.pack(fill="x", pady=(6, 0))
        self.card_attr = CollapsibleCard(
            attr_wrap,
            "Mouse Attribute",
            width=262,
            expanded=False,
            on_toggle=lambda _: self._update_right_scroll(),
        )
        self.card_attr.pack(fill="x")
        self._build_mouse_attr_card(self.card_attr.body)

        # 5. Power Management (expandido na referência)
        pm_wrap = tk.Frame(self.right_inner, bg=BG_MAIN)
        pm_wrap.pack(fill="x", pady=(6, 0))
        self.card_pm = CollapsibleCard(
            pm_wrap,
            "Power Management",
            width=262,
            expanded=True,
            on_toggle=lambda _: self._update_right_scroll(),
        )
        self.card_pm.pack(fill="x")
        self._build_power_mgmt_card(self.card_pm.body)

        # 6. Key Response Time (expandido na referência)
        deb_wrap = tk.Frame(self.right_inner, bg=BG_MAIN)
        deb_wrap.pack(fill="x", pady=(6, 0))
        self.card_debounce = CollapsibleCard(
            deb_wrap,
            "Key Response Time",
            width=262,
            expanded=True,
            on_toggle=lambda _: self._update_right_scroll(),
        )
        self.card_debounce.pack(fill="x")
        self._build_debounce_card(self.card_debounce.body)

        # 7. Ripple Control (expandido na referência)
        rip_wrap = tk.Frame(self.right_inner, bg=BG_MAIN)
        rip_wrap.pack(fill="x", pady=(6, 0))
        self.card_ripple = CollapsibleCard(
            rip_wrap,
            "Ripple Control",
            width=262,
            expanded=True,
            on_toggle=lambda _: self._update_right_scroll(),
        )
        self.card_ripple.pack(fill="x")
        self._build_ripple_card(self.card_ripple.body)

        # 8. Angle Snap (expandido na referência)
        ang_wrap = tk.Frame(self.right_inner, bg=BG_MAIN)
        ang_wrap.pack(fill="x", pady=(6, 0))
        self.card_angle = CollapsibleCard(
            ang_wrap,
            "Angle Snap",
            width=262,
            expanded=True,
            on_toggle=lambda _: self._update_right_scroll(),
        )
        self.card_angle.pack(fill="x")
        self._build_angle_card(self.card_angle.body)

    def _build_dpi_card(self, body: tk.Frame) -> None:
        cols_frame = tk.Frame(body, bg=BG_CARD, padx=5, pady=4)
        cols_frame.pack(fill="x")

        self.dpi_sliders: list[VerticalDpiSlider] = []
        self.dpi_entries: list[tk.Entry] = []
        self.dpi_dots: list[RadioDot] = []
        self.dpi_color_bars: list[tk.Canvas] = []

        for i in range(6):
            col = tk.Frame(cols_frame, bg=BG_CARD, width=41)
            col.pack(side="left", padx=1)

            slider = VerticalDpiSlider(
                col,
                min_val=1,
                max_val=320,
                value=16,
                height=104,
                width=38,
                on_change=lambda pos, idx=i: self._on_dpi_slider_move(idx, pos),
            )
            slider.pack()
            self.dpi_sliders.append(slider)

            # Label "100" acima do campo branco, exatamente como na screenshot
            lbl_step = tk.Label(
                col,
                text="100",
                bg=BG_CARD,
                fg=TEXT_WHITE,
                font=("Arial", 8),
            )
            lbl_step.pack(pady=(0, 1))

            ent = tk.Entry(
                col,
                width=5,
                bg=TEXT_WHITE,
                fg="#000000",
                insertbackground="#000000",
                justify="center",
                relief="flat",
                font=("Arial", 8, "bold"),
            )
            ent.pack(ipady=1)
            ent.bind("<Return>", lambda _e, idx=i: self._on_dpi_entry_commit(idx))
            ent.bind("<FocusOut>", lambda _e, idx=i: self._on_dpi_entry_commit(idx))
            self.dpi_entries.append(ent)

            dot = RadioDot(
                col,
                "",
                selected=(i == 1),
                command=lambda idx=i: self._on_select_dpi_stage(idx + 1),
                width=36,
                height=18,
            )
            dot.pack(pady=(2, 0))
            # Clique direito no ponto abre seletor de cor RGB do estágio
            dot.bind("<Button-3>", lambda _e, idx=i: self._pick_stage_color(idx))
            self.dpi_dots.append(dot)

        apply_row = tk.Frame(body, bg=BG_CARD, pady=4)
        apply_row.pack(fill="x")
        self.apply_dpi_btn = DuiButton(
            apply_row,
            "Apply",
            command=self._apply_dpi_to_hardware,
            width=76,
            height=22,
        )
        self.apply_dpi_btn.pack()

    def _build_light_card(self, body: tk.Frame) -> None:
        wrap = tk.Frame(body, bg=BG_CARD, padx=12, pady=10)
        wrap.pack(fill="x")

        r1 = tk.Frame(wrap, bg=BG_CARD)
        r1.pack(fill="x", pady=(0, 6))
        tk.Label(r1, text="Mode:", bg=BG_CARD, fg=TEXT_WHITE, font=("Arial", 9), width=10, anchor="w").pack(side="left")
        self.light_mode_btn = DuiButton(
            r1,
            "Color Breathing",
            command=self._open_light_mode_menu,
            width=155,
            height=22,
        )
        self.light_mode_btn.pack(side="left")

        r2 = tk.Frame(wrap, bg=BG_CARD)
        r2.pack(fill="x", pady=4)
        tk.Label(r2, text="Brightness:", bg=BG_CARD, fg=TEXT_WHITE, font=("Arial", 9), anchor="w").pack(anchor="w")
        self.light_bright_slider = HorizontalRedSlider(
            r2,
            min_val=1,
            max_val=8,
            value=8,
            width=210,
            height=18,
            on_release=lambda _v: self._apply_aux_to_hardware(),
        )
        self.light_bright_slider.pack(pady=(2, 0))

        r3 = tk.Frame(wrap, bg=BG_CARD)
        r3.pack(fill="x", pady=4)
        tk.Label(r3, text="Speed:", bg=BG_CARD, fg=TEXT_WHITE, font=("Arial", 9), anchor="w").pack(anchor="w")
        self.light_speed_slider = HorizontalRedSlider(
            r3,
            min_val=4,
            max_val=8,
            value=8,
            width=210,
            height=18,
            on_release=lambda _v: self._apply_aux_to_hardware(),
        )
        self.light_speed_slider.pack(pady=(2, 0))

        r4 = tk.Frame(wrap, bg=BG_CARD)
        r4.pack(fill="x", pady=(6, 2))
        tk.Label(r4, text="Color:", bg=BG_CARD, fg=TEXT_WHITE, font=("Arial", 9), width=8, anchor="w").pack(side="left")
        self.light_color_swatch = tk.Canvas(
            r4,
            width=24,
            height=18,
            bg="#00ff00",
            highlightthickness=1,
            highlightbackground="#8a8d90",
            cursor="hand2",
        )
        self.light_color_swatch.pack(side="left")
        self.light_color_swatch.bind("<Button-1>", lambda _e: self._pick_light_color())

    def _build_polling_card(self, body: tk.Frame) -> None:
        wrap = tk.Frame(body, bg=BG_CARD, padx=14, pady=10)
        wrap.pack(fill="x")
        self.polling_dots: dict[int, RadioDot] = {}
        modes = [
            (125, "125 Hz (Power Saving)"),
            (250, "250 Hz (Office)"),
            (500, "500 Hz (Gaming)"),
            (1000, "1000 Hz (E-sports)"),
        ]
        for hz, label in modes:
            d = RadioDot(
                wrap,
                label,
                selected=(hz == 1000),
                command=lambda val=hz: self._on_select_polling(val),
                width=220,
                height=22,
            )
            d.pack(anchor="w", pady=2)
            self.polling_dots[hz] = d

    def _build_mouse_attr_card(self, body: tk.Frame) -> None:
        wrap = tk.Frame(body, bg=BG_CARD, padx=14, pady=10)
        wrap.pack(fill="x")
        DuiButton(
            wrap,
            "Open Mouse Attribute",
            command=self._open_system_mouse_settings,
            width=230,
            height=24,
        ).pack()

    def _build_power_mgmt_card(self, body: tk.Frame) -> None:
        wrap = tk.Frame(body, bg=BG_CARD, padx=18, pady=6)
        wrap.pack(fill="x")

        self.sleep_slider = HorizontalRedSlider(
            wrap,
            min_val=1,
            max_val=60,
            value=1,
            width=200,
            height=18,
            on_change=self._on_sleep_slider_move,
            on_release=lambda _v: self._apply_aux_to_hardware(),
        )
        self.sleep_slider.pack()

        self.sleep_label = tk.Label(
            wrap,
            text="Sleep Time:0.5 Min",
            bg=BG_CARD,
            fg=TEXT_WHITE,
            font=("Arial", 8),
        )
        self.sleep_label.pack(pady=(1, 5))

        self.deep_sleep_slider = HorizontalRedSlider(
            wrap,
            min_val=1,
            max_val=60,
            value=5,
            width=200,
            height=18,
            on_change=self._on_deep_sleep_slider_move,
            on_release=lambda _v: self._apply_aux_to_hardware(),
        )
        self.deep_sleep_slider.pack()

        self.deep_sleep_label = tk.Label(
            wrap,
            text="Deep Sleep Time:5 Min",
            bg=BG_CARD,
            fg=TEXT_WHITE,
            font=("Arial", 8),
        )
        self.deep_sleep_label.pack(pady=(1, 1))

    def _build_debounce_card(self, body: tk.Frame) -> None:
        wrap = tk.Frame(body, bg=BG_CARD, padx=12, pady=6)
        wrap.pack(fill="x")

        self.debounce_slider = HorizontalRedSlider(
            wrap,
            min_val=1,
            max_val=15,
            value=2,
            width=172,
            height=18,
            on_change=self._on_debounce_slider_move,
            on_release=lambda _v: self._apply_aux_to_hardware(),
        )
        self.debounce_slider.pack(side="left", padx=(4, 10))

        self.debounce_box = tk.Label(
            wrap,
            text="4 MS",
            width=6,
            bg=TEXT_WHITE,
            fg="#000000",
            font=("Arial", 8, "bold"),
            pady=1,
        )
        self.debounce_box.pack(side="left")

    def _build_ripple_card(self, body: tk.Frame) -> None:
        wrap = tk.Frame(body, bg=BG_CARD, padx=16, pady=6)
        wrap.pack(fill="x")
        self.ripple_off_dot = RadioDot(
            wrap,
            "Off",
            selected=False,
            command=lambda: self._set_ripple(False),
            width=95,
            height=18,
        )
        self.ripple_off_dot.pack(side="left")
        self.ripple_on_dot = RadioDot(
            wrap,
            "On",
            selected=True,
            command=lambda: self._set_ripple(True),
            width=95,
            height=18,
        )
        self.ripple_on_dot.pack(side="left", padx=(10, 0))

    def _build_angle_card(self, body: tk.Frame) -> None:
        wrap = tk.Frame(body, bg=BG_CARD, padx=16, pady=6)
        wrap.pack(fill="x")
        self.angle_off_dot = RadioDot(
            wrap,
            "Off",
            selected=False,
            command=lambda: self._set_angle_snap(False),
            width=95,
            height=18,
        )
        self.angle_off_dot.pack(side="left")
        self.angle_on_dot = RadioDot(
            wrap,
            "On",
            selected=True,
            command=lambda: self._set_angle_snap(True),
            width=95,
            height=18,
        )
        self.angle_on_dot.pack(side="left", padx=(10, 0))

    # ------------------------------------------------------------------
    # Scrollbar customizada da coluna direita
    # ------------------------------------------------------------------
    def _update_right_scroll(self, _event=None) -> None:
        self.right_canvas.update_idletasks()
        bbox = self.right_canvas.bbox("all")
        if not bbox:
            return
        total_h = max(1, bbox[3] - bbox[1])
        vis_h = max(1, self.right_canvas.winfo_height())
        self.right_canvas.configure(scrollregion=bbox)

        self.right_scroll.delete("all")
        if total_h <= vis_h:
            self.right_scroll.create_rectangle(1, 0, 5, vis_h, fill="#0a9396", outline="")
        else:
            top_frac, bot_frac = self.right_canvas.yview()
            y1 = int(top_frac * vis_h)
            y2 = max(y1 + 24, int(bot_frac * vis_h))
            self.right_scroll.create_rectangle(1, y1, 5, y2, fill="#00f5d4", outline="")

    def _on_mousewheel_up(self, event) -> None:
        if event.x_root >= self.right_canvas.winfo_rootx():
            self.right_canvas.yview_scroll(-1, "units")
            self._update_right_scroll()

    def _on_mousewheel_down(self, event) -> None:
        if event.x_root >= self.right_canvas.winfo_rootx():
            self.right_canvas.yview_scroll(1, "units")
            self._update_right_scroll()

    def _on_mousewheel_win(self, event) -> None:
        if event.x_root >= self.right_canvas.winfo_rootx():
            self.right_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
            self._update_right_scroll()

    # ------------------------------------------------------------------
    # Renderização de Widgets Customizados (Lista de Perfis e Bateria em Tempo Real)
    # ------------------------------------------------------------------
    def _draw_profile_list(self) -> None:
        c = self.profile_canvas
        c.delete("all")
        row_h = 22
        for idx, prof in enumerate(self.profiles):
            y1 = 2 + idx * row_h
            y2 = y1 + row_h
            if idx == self.active_profile_idx:
                # Barra degradê Teal/Cyan Elétrico do novo esquema de cores
                c.create_rectangle(2, y1, 228, y1 + 11, fill="#0d3b42", outline="")
                c.create_rectangle(2, y1 + 11, 228, y2 - 1, fill="#135660", outline="")
                c.create_line(2, y2 - 1, 228, y2 - 1, fill="#00f5d4")
            c.create_text(
                10,
                (y1 + y2) // 2,
                text=prof.get("name", f"Profile{idx + 1}"),
                anchor="w",
                fill=TEXT_WHITE,
                font=("Arial", 9, "bold" if idx == self.active_profile_idx else "normal"),
            )

    @staticmethod
    def _lerp_hex(c1: str, c2: str, t: float) -> str:
        t = max(0.0, min(1.0, t))
        a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
        b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
        return "#" + "".join(f"{int(x + (y - x) * t):02x}" for x, y in zip(a, b))

    @staticmethod
    def _fmt_elapsed(seconds: float) -> str:
        m = int(seconds // 60)
        if m < 1:
            return "agora"
        if m < 60:
            return f"há {m} min"
        return f"há {m // 60}h{m % 60:02d}"

    def _draw_battery(self) -> None:
        """Desenha o card de bateria a partir de self.battery (somente dados reais)."""
        import math

        bat = self.battery
        c = self.battery_canvas
        c.delete("all")
        now = time.monotonic()
        level = bat.level
        w = 260
        cx = w // 2
        bx1, by1, bx2, by2 = cx - 62, 10, cx + 54, 44
        ix1, iy1, ix2, iy2 = bx1 + 3, by1 + 3, bx2 - 3, by2 - 3
        max_w = ix2 - ix1
        base_w = int(round(max_w * ((level or 0) / 100.0)))

        # Paleta por estado
        if bat.is_full:
            border, grad = "#34d399", ("#10b981", "#6ee7b7")
        elif bat.is_charging:
            border, grad = "#00f5d4", ("#0284c7", "#00f5d4")
        elif bat.waiting_reading:
            border, grad = "#5b7c84", ("#35505a", "#4f6f78")
        elif (level or 0) <= 20:
            border, grad = "#f43f5e", ("#e11d48", "#fb923c")
        elif (level or 0) <= 45:
            border, grad = "#f59e0b", ("#f59e0b", "#facc15")
        else:
            border, grad = "#64dfdf", ("#0891b2", "#34d399")

        # Respiração suave do contorno (carregando / aguardando leitura)
        if bat.is_charging or bat.waiting_reading:
            breath = 0.5 + 0.5 * math.sin(now * 2 * math.pi / 2.4)
            halo = self._lerp_hex("#0d2a30", "#145f66" if bat.is_charging else "#2f4a52", breath)
            c.create_rectangle(bx1 - 3, by1 - 3, bx2 + 3, by2 + 3, outline=halo, width=2)

        c.create_rectangle(bx1, by1, bx2, by2, fill="#091316", outline=border, width=2)
        c.create_rectangle(bx2 + 2, (by1 + by2) // 2 - 7, bx2 + 7, (by1 + by2) // 2 + 7,
                           fill=border, outline=border)
        c.create_rectangle(ix1, iy1, ix2, iy2, fill="#0f1c21", outline="")

        def gradient(x_from: int, x_to: int, c_a: str, c_b: str) -> None:
            step = 2
            for x in range(x_from, x_to, step):
                t = (x - ix1) / max(1, max_w - 1)
                c.create_rectangle(x, iy1, min(x + step, x_to), iy2,
                                   fill=self._lerp_hex(c_a, c_b, t), outline="")

        if bat.is_full:
            gradient(ix1, ix2, *grad)
        elif bat.is_charging:
            # Nível medido antes da carga (base) + fluxo de energia animado até o fim da célula.
            gradient(ix1, ix1 + base_w, "#0a4f73", "#0b7f86")
            period = 2.2
            phase = (now % period) / period
            eased = 1 - (1 - phase) ** 3            # ease-out cúbico: acelera e assenta suave
            flow_end = ix1 + base_w + int((max_w - base_w) * eased)
            if flow_end > ix1 + base_w:
                gradient(ix1 + base_w, flow_end, *grad)
                # brilho na frente do fluxo
                c.create_rectangle(max(ix1, flow_end - 4), iy1, flow_end, iy2,
                                   fill=self._lerp_hex("#00f5d4", "#ffffff", 0.6), outline="")
        else:
            if base_w > 0:
                gradient(ix1, ix1 + base_w, *grad)

        for frac in (0.25, 0.5, 0.75):
            dx = ix1 + int(round(max_w * frac))
            c.create_line(dx, iy1, dx, iy2, fill="#081013")

        if bat.is_charging:
            bxc, byc = (ix1 + ix2) // 2, (iy1 + iy2) // 2
            c.create_polygon(bxc + 3, byc - 11, bxc - 5, byc + 1, bxc - 1, byc + 1,
                             bxc - 3, byc + 11, bxc + 5, byc - 1, bxc + 1, byc - 1,
                             fill="#ffffff", outline="#062228", width=1.2)

        # ---- Textos ----
        lvl_txt = f"{level}%" if level is not None else "--%"
        if bat.is_full:
            l1, l1c = "100%", "#34d399"
            l2, l2c = "● CARGA COMPLETA", "#34d399"
            l3 = "Pode desconectar o cabo"
        elif bat.is_charging:
            dots = "." * (int(now * 2) % 4)
            if level is not None:
                l1 = f"⚡ Carregando{dots:<3} ({level}%)"
            else:
                l1 = f"⚡ Carregando{dots:<3}"
            l1c = "#00f5d4"
            origem = "via cabo USB" if bat.mode == "charging_cable" else "na base/carregador"
            l2 = f"{origem} • iniciado {self._fmt_elapsed(bat.charge_elapsed_s(now))}"
            l2c = "#72efdd"
            l3 = (f"Nível medido antes da carga: {lvl_txt}"
                  if level is not None else "O mouse atualiza a medição ao desconectar")
        elif bat.waiting_reading:
            l1, l1c = (f"~{lvl_txt}" if level is not None else "--%"), "#8fb3ba"
            dots = "." * (int(now * 2) % 4)
            l2, l2c = f"● Atualizando nível{dots:<3}", "#8fb3ba"
            l3 = ("Valor antigo; aguardando nova leitura do mouse (2.4G)"
                  if level is not None else "Aguardando a primeira leitura do mouse (2.4G)")
        else:
            l1 = lvl_txt
            l1c = "#fb7185" if (level or 0) <= 20 else TEXT_WHITE
            l2 = "● BATERIA EM USO (2.4G)"
            l2c = "#fb7185" if (level or 0) <= 20 else "#5eead4"
            l3 = f"Leitura real do mouse • {time.strftime('%H:%M', time.localtime(bat.level_wall_ts))}"

        c.create_text(cx, 60, text=l1, fill=l1c, font=("Arial", 14, "bold"))
        c.create_text(cx, 81, text=l2, fill=l2c, font=("Arial", 8, "bold"))
        c.create_text(cx, 97, text=l3, fill="#6f949c", font=("Arial", 7), width=250)

    def _tick_charging_animation(self) -> None:
        """Anima (~30 fps) apenas enquanto carrega ou aguarda leitura; parado no resto."""
        try:
            if self.battery.is_charging or self.battery.waiting_reading:
                self._draw_battery()
        except Exception:
            pass
        finally:
            self.root.after(33, self._tick_charging_animation)

    def _format_button_action(self, code: int) -> str:
        if code in config.BUTTON_ACTION_LABELS:
            return config.BUTTON_ACTION_LABELS[code]
        for m in self.custom_macros:
            if m.get("code") == code:
                return f"Macro: {m.get('name', 'Key')}"
        if code >= 0x10000:
            mod = (code >> 8) & 0xFF
            usage = code & 0xFF
            parts: list[str] = []
            if mod & 0x01:
                parts.append("Ctrl")
            if mod & 0x02:
                parts.append("Shift")
            if mod & 0x04:
                parts.append("Alt")
            if mod & 0x08:
                parts.append("Super")
            parts.append(HID_USAGE_TO_NAME.get(usage, f"0x{usage:02X}"))
            return "Macro: " + "+".join(parts)
        return "Left Click"

    # ------------------------------------------------------------------
    # Sincronização entre Perfil <-> Widgets
    # ------------------------------------------------------------------
    def _apply_profile_to_widgets(self, prof: dict) -> None:
        # Botões 1..5
        btns = prof.get("buttons", [0x01, 0x02, 0x03, 0x04, 0x05])
        for i in range(5):
            code = btns[i] if i < len(btns) else 0x01
            self.key_buttons[i].set_text(self._format_button_action(code))

        # Estágios DPI
        dpis = prof.get("stage_dpis", [800, 1600, 2400, 3200, 5000, 22000])
        active_stage = int(prof.get("active_stage", 2))
        for i in range(6):
            val = config.snap_dpi(dpis[i] if i < len(dpis) else 800)
            pos = config.dpi_to_pos(val)
            self.dpi_sliders[i].set_value(pos, notify=False)
            self.dpi_entries[i].delete(0, "end")
            self.dpi_entries[i].insert(0, str(val))
            self.dpi_dots[i].set_selected((i + 1) == active_stage)

        # Iluminação
        lmode = int(prof.get("light_mode", 4))
        self.light_mode_btn.set_text(config.LIGHT_MODE_NAMES.get(lmode, "Color Breathing"))
        self.light_bright_slider.set_value(int(prof.get("light_brightness", 8)))
        self.light_speed_slider.set_value(int(prof.get("light_speed", 8)))
        lcol = prof.get("light_color", [0, 255, 0])
        self.light_color_swatch.configure(bg=f"#{lcol[0]:02x}{lcol[1]:02x}{lcol[2]:02x}")

        # Polling rate
        hz = int(prof.get("polling_hz", 1000))
        for h, dot in self.polling_dots.items():
            dot.set_selected(h == hz)

        # Power Management (Sleep & Deep Sleep)
        slp = int(prof.get("sleep_time", 1))
        dslp = int(prof.get("deep_sleep_time", 5))
        self.sleep_slider.set_value(slp)
        self.sleep_label.configure(text=f"Sleep Time:{slp * 0.5:g} Min")
        self.deep_sleep_slider.set_value(dslp)
        self.deep_sleep_label.configure(text=f"Deep Sleep Time:{dslp} Min")

        # Key Response Time (Debounce)
        deb = int(prof.get("debounce_ms", 4))
        self.debounce_slider.set_value(max(1, min(15, deb // 2)))
        self.debounce_box.configure(text=f"{deb} MS")

        # Ripple Control & Angle Snap
        rip = bool(prof.get("ripple_control", True))
        self.ripple_off_dot.set_selected(not rip)
        self.ripple_on_dot.set_selected(rip)

        ang = bool(prof.get("angle_snap", True))
        self.angle_off_dot.set_selected(not ang)
        self.angle_on_dot.set_selected(ang)

        # Lista de Perfis e Bateria (a bateria é do dispositivo, não muda com o perfil)
        self._draw_profile_list()
        self._draw_battery()
        self._draw_center_canvas()

    # ------------------------------------------------------------------
    # Eventos de Interação da GUI
    # ------------------------------------------------------------------
    def _open_button_menu(self, btn_idx: int) -> None:
        menu = tk.Menu(
            self.root,
            tearoff=0,
            bg="#0d181b",
            fg=TEXT_WHITE,
            activebackground="#0a9396",
            activeforeground=TEXT_WHITE,
            bd=1,
            relief="solid",
        )
        for label, target in BUTTON_MENU_STRUCTURE:
            if isinstance(target, list):
                sub = tk.Menu(
                    menu,
                    tearoff=0,
                    bg="#0d181b",
                    fg=TEXT_WHITE,
                    activebackground="#0a9396",
                    activeforeground=TEXT_WHITE,
                )
                for sub_label, code in target:
                    sub.add_command(
                        label=sub_label,
                        command=lambda c=code, idx=btn_idx: self._set_button_action(idx, c),
                    )
                menu.add_cascade(label=label, menu=sub)
            else:
                menu.add_command(
                    label=label,
                    command=lambda c=target, idx=btn_idx: self._set_button_action(idx, c),
                )

        # Submenu Macro
        macro_sub = tk.Menu(
            menu,
            tearoff=0,
            bg="#0d181b",
            fg=TEXT_WHITE,
            activebackground="#0a9396",
            activeforeground=TEXT_WHITE,
        )
        for m in self.custom_macros:
            m_name = m.get("name", "Macro")
            m_code = int(m.get("code", 0x01))
            macro_sub.add_command(
                label=m_name,
                command=lambda c=m_code, idx=btn_idx: self._set_button_action(idx, c),
            )
        if self.custom_macros:
            macro_sub.add_separator()
        macro_sub.add_command(
            label="Open Macro Manager...",
            command=self._open_macro_dialog,
        )
        menu.add_cascade(label="Macro", menu=macro_sub)
        menu.add_separator()
        menu.add_command(
            label="Restore Default Buttons & Wheel",
            command=self._restore_default_buttons,
        )

        w = self.key_buttons[btn_idx]
        menu.tk_popup(w.winfo_rootx(), w.winfo_rooty() + w.winfo_height())

    def _set_button_action(self, btn_idx: int, action_code: int) -> None:
        btns = list(self.current_profile.get("buttons", [0x01, 0x02, 0x03, 0x04, 0x05]))
        old_code = btns[btn_idx]
        btns[btn_idx] = action_code
        if 0x01 not in btns:
            messagebox.showwarning(
                "WaleAttack",
                'At least one button must be "Left Click"!',
                parent=self.root,
            )
            btns[btn_idx] = old_code
            return
        self.current_profile["buttons"] = btns
        label_str = self._format_button_action(action_code)
        self.key_buttons[btn_idx].set_text(label_str)
        self._save_profiles()
        pkt = config.build_button_report(btns)
        self._write_reports_async([pkt], f"Button {btn_idx + 1} -> {label_str}")

    def _restore_default_buttons(self) -> None:
        default_btns = [0x01, 0x02, 0x03, 0x04, 0x05]
        self.current_profile["buttons"] = list(default_btns)
        for i, code in enumerate(default_btns):
            self.key_buttons[i].set_text(self._format_button_action(code))
        self._save_profiles()
        pkt08 = config.build_button_report(default_btns)
        self._write_reports_async([pkt08], "Default buttons (1..5) and Scroll Wheel restored!")

    def _on_dpi_slider_move(self, idx: int, pos: int) -> None:
        dpi = config.pos_to_dpi(pos)
        self.dpi_entries[idx].delete(0, "end")
        self.dpi_entries[idx].insert(0, str(dpi))
        self.current_profile["stage_dpis"][idx] = dpi

    def _on_dpi_entry_commit(self, idx: int) -> None:
        txt = self.dpi_entries[idx].get().strip()
        try:
            dpi = config.snap_dpi(int(txt))
        except ValueError:
            dpi = self.current_profile["stage_dpis"][idx]
        pos = config.dpi_to_pos(dpi)
        self.dpi_sliders[idx].set_value(pos, notify=False)
        self.dpi_entries[idx].delete(0, "end")
        self.dpi_entries[idx].insert(0, str(dpi))
        self.current_profile["stage_dpis"][idx] = dpi
        self._save_profiles()

    def _on_select_dpi_stage(self, stage_num: int) -> None:
        self.current_profile["active_stage"] = stage_num
        for i, dot in enumerate(self.dpi_dots):
            dot.set_selected((i + 1) == stage_num)
        self._save_profiles()
        self._apply_dpi_to_hardware()

    def _pick_stage_color(self, idx: int) -> None:
        cur = self.current_profile["stage_colors"][idx]
        init_hex = f"#{cur[0]:02x}{cur[1]:02x}{cur[2]:02x}"
        rgb, _hex = colorchooser.askcolor(
            color=init_hex,
            title=f"Stage {idx + 1} RGB Color",
            parent=self.root,
        )
        if rgb:
            self.current_profile["stage_colors"][idx] = [int(rgb[0]), int(rgb[1]), int(rgb[2])]
            self._save_profiles()
            self._apply_dpi_to_hardware()

    def _apply_dpi_to_hardware(self) -> None:
        for i in range(6):
            self._on_dpi_entry_commit(i)
        self._save_profiles()

        def worker():
            with self._io_lock:
                dev = self._open_dev()
                if dev is None:
                    return
                with dev:
                    self._ensure_mouse_awake(dev)
                    base = self.raw04 or protocol.read_report(dev, 0x04, 55, 1)
                    colors = [tuple(c) for c in self.current_profile["stage_colors"]]
                    updated = config.update_all_stages(
                        base,
                        self.current_profile["stage_dpis"],
                        active_stage=int(self.current_profile["active_stage"]),
                        stage_colors=colors,
                    )
                    updated = config.update_sensor_flags(
                        updated,
                        angle_snap=bool(self.current_profile["angle_snap"]),
                        ripple_control=bool(self.current_profile["ripple_control"]),
                    )
                    protocol.write_report(dev, updated)
                    time.sleep(0.03)
                    protocol.write_report(dev, updated)
                    self.raw04 = updated
            stage = self.current_profile["active_stage"]
            dpi = self.current_profile["stage_dpis"][stage - 1]
            self._set_status(f"DPI Settings applied (Active: Stage {stage} @ {dpi} DPI)")

        threading.Thread(target=self._safe_run, args=(worker,), daemon=True).start()

    def _open_light_mode_menu(self) -> None:
        menu = tk.Menu(
            self.root,
            tearoff=0,
            bg="#0d181b",
            fg=TEXT_WHITE,
            activebackground="#0a9396",
            activeforeground=TEXT_WHITE,
        )
        for mode_id, name in config.LIGHT_MODE_NAMES.items():
            menu.add_command(
                label=name,
                command=lambda m=mode_id: self._set_light_mode(m),
            )
        w = self.light_mode_btn
        menu.tk_popup(w.winfo_rootx(), w.winfo_rooty() + w.winfo_height())

    def _set_light_mode(self, mode_id: int) -> None:
        self.current_profile["light_mode"] = mode_id
        self.light_mode_btn.set_text(config.LIGHT_MODE_NAMES.get(mode_id, "Static"))
        self._save_profiles()
        self._apply_aux_to_hardware()

    def _pick_light_color(self) -> None:
        cur = self.current_profile.get("light_color", [0, 255, 0])
        init_hex = f"#{cur[0]:02x}{cur[1]:02x}{cur[2]:02x}"
        rgb, hex_str = colorchooser.askcolor(
            color=init_hex,
            title="Light RGB Color",
            parent=self.root,
        )
        if rgb and hex_str:
            self.current_profile["light_color"] = [int(rgb[0]), int(rgb[1]), int(rgb[2])]
            self.light_color_swatch.configure(bg=hex_str)
            self._save_profiles()
            self._apply_aux_to_hardware()

    def _on_select_polling(self, hz: int) -> None:
        self.current_profile["polling_hz"] = hz
        for h, dot in self.polling_dots.items():
            dot.set_selected(h == hz)
        self._save_profiles()
        pkt = config.build_polling_report(hz)
        self._write_reports_async([pkt], f"Polling Rate -> {hz} Hz")

    def _on_sleep_slider_move(self, val: int) -> None:
        self.current_profile["sleep_time"] = val
        self.sleep_label.configure(text=f"Sleep Time:{val * 0.5:g} Min")

    def _on_deep_sleep_slider_move(self, val: int) -> None:
        self.current_profile["deep_sleep_time"] = val
        self.deep_sleep_label.configure(text=f"Deep Sleep Time:{val} Min")

    def _on_debounce_slider_move(self, val: int) -> None:
        ms = val * 2
        self.current_profile["debounce_ms"] = ms
        self.debounce_box.configure(text=f"{ms} MS")

    def _apply_aux_to_hardware(self) -> None:
        self.current_profile["light_brightness"] = self.light_bright_slider.value
        self.current_profile["light_speed"] = self.light_speed_slider.value
        self.current_profile["sleep_time"] = self.sleep_slider.value
        self.current_profile["deep_sleep_time"] = self.deep_sleep_slider.value
        self.current_profile["debounce_ms"] = self.debounce_slider.value * 2
        self._save_profiles()

        def worker():
            with self._io_lock:
                dev = self._open_dev()
                if dev is None:
                    return
                with dev:
                    self._ensure_mouse_awake(dev)
                    base = self.raw05 or protocol.read_report(dev, 0x05, 14, 1)
                    lc = self.current_profile.get("light_color", [0, 255, 0])
                    updated = config.update_aux_config(
                        base,
                        light_mode=int(self.current_profile["light_mode"]),
                        light_brightness=int(self.current_profile["light_brightness"]),
                        light_speed=int(self.current_profile["light_speed"]),
                        light_color=(lc[0], lc[1], lc[2]),
                        sleep_time=int(self.current_profile["sleep_time"]),
                        deep_sleep_time=int(self.current_profile["deep_sleep_time"]),
                        debounce_ms=int(self.current_profile["debounce_ms"]),
                    )
                    protocol.write_report(dev, updated)
                    time.sleep(0.03)
                    protocol.write_report(dev, updated)
                    self.raw05 = updated
            self._set_status(
                f"Power/Debounce/Light updated ({self.current_profile['debounce_ms']} ms, "
                f"Sleep {self.current_profile['sleep_time'] * 0.5:g}m / {self.current_profile['deep_sleep_time']}m)"
            )

        threading.Thread(target=self._safe_run, args=(worker,), daemon=True).start()

    def _set_ripple(self, enabled: bool) -> None:
        self.current_profile["ripple_control"] = enabled
        self.ripple_off_dot.set_selected(not enabled)
        self.ripple_on_dot.set_selected(enabled)
        self._save_profiles()
        self._apply_dpi_to_hardware()

    def _set_angle_snap(self, enabled: bool) -> None:
        self.current_profile["angle_snap"] = enabled
        self.angle_off_dot.set_selected(not enabled)
        self.angle_on_dot.set_selected(enabled)
        self._save_profiles()
        self._apply_dpi_to_hardware()

    # ------------------------------------------------------------------
    # Gerenciamento de Perfis (Add, Delete, Rename, Import, Export, Reset)
    # ------------------------------------------------------------------
    def _on_profile_list_click(self, event) -> None:
        idx = (event.y - 2) // 22
        if 0 <= idx < len(self.profiles) and idx != self.active_profile_idx:
            self.active_profile_idx = idx
            self._save_profiles()
            self._apply_profile_to_widgets(self.current_profile)
            self._apply_full_profile_to_hardware()

    def _profile_add(self) -> None:
        default_name = f"Profile{len(self.profiles) + 1}"
        name = simpledialog.askstring(
            "Add Profile",
            "Input Name:",
            initialvalue=default_name,
            parent=self.root,
        )
        if not name or not name.strip():
            return
        name = name.strip()
        if any(p.get("name") == name for p in self.profiles):
            messagebox.showwarning("Warning!", "The name is duplicate, please re-enter!", parent=self.root)
            return
        self.profiles.append(default_profile_dict(name))
        self.active_profile_idx = len(self.profiles) - 1
        self._save_profiles()
        self._apply_profile_to_widgets(self.current_profile)

    def _profile_delete(self) -> None:
        if len(self.profiles) <= 1:
            messagebox.showwarning("Warning!", "Keep at least one configuration file!", parent=self.root)
            return
        if not messagebox.askyesno("Warning!", "Do you really want to delete this profile?", parent=self.root):
            return
        del self.profiles[self.active_profile_idx]
        self.active_profile_idx = max(0, self.active_profile_idx - 1)
        self._save_profiles()
        self._apply_profile_to_widgets(self.current_profile)

    def _profile_rename(self) -> None:
        cur_name = self.current_profile.get("name", "Profile1")
        name = simpledialog.askstring(
            "Edit Profile",
            "Input Name:",
            initialvalue=cur_name,
            parent=self.root,
        )
        if not name or not name.strip():
            return
        self.current_profile["name"] = name.strip()
        self._save_profiles()
        self._draw_profile_list()

    def _profile_import(self) -> None:
        path = filedialog.askopenfilename(
            title="Import Profile",
            filetypes=[("WaleAttack Profile", "*.json"), ("All Files", "*.*")],
            parent=self.root,
        )
        if not path:
            return
        try:
            prof = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(prof, dict) or "stage_dpis" not in prof:
                raise ValueError("Invalid profile format")
            self.profiles.append(prof)
            self.active_profile_idx = len(self.profiles) - 1
            self._save_profiles()
            self._apply_profile_to_widgets(self.current_profile)
            self._apply_full_profile_to_hardware()
        except Exception as exc:
            messagebox.showerror("Import Error", str(exc), parent=self.root)

    def _profile_export(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export Profile",
            defaultextension=".json",
            initialfile=f"{self.current_profile.get('name', 'Profile1')}.json",
            filetypes=[("WaleAttack Profile", "*.json")],
            parent=self.root,
        )
        if not path:
            return
        try:
            Path(path).write_text(json.dumps(self.current_profile, indent=2), encoding="utf-8")
            self._set_status(f"Exported profile to {Path(path).name}")
        except Exception as exc:
            messagebox.showerror("Export Error", str(exc), parent=self.root)

    def _reset_profile_action(self) -> None:
        if not messagebox.askyesno(
            "Warning!",
            "Are you sure you want to restore this configuration to the default settings?",
            parent=self.root,
        ):
            return
        name = self.current_profile.get("name", "Profile1")
        self.profiles[self.active_profile_idx] = default_profile_dict(name)
        self._save_profiles()
        self._apply_profile_to_widgets(self.current_profile)
        self._apply_full_profile_to_hardware()

    def _apply_full_profile_to_hardware(self) -> None:
        self._apply_dpi_to_hardware()
        self._apply_aux_to_hardware()
        pkt06 = config.build_polling_report(int(self.current_profile["polling_hz"]))
        pkt08 = config.build_button_report(self.current_profile["buttons"])
        self._write_reports_async([pkt06, pkt08], "Profile synchronized with mouse")

    def _open_macro_dialog(self) -> None:
        dlg = tk.Toplevel(self.root)
        dlg.title("WaleAttack - Macro Manager")
        dlg.configure(bg=BG_CARD)
        dlg.geometry("460x340")
        dlg.transient(self.root)

        tk.Label(
            dlg,
            text="Macro Manager (Custom Key / Combo)",
            bg=BG_HEADER_OPEN,
            fg=TEXT_WHITE,
            font=("Arial", 10, "bold"),
            anchor="w",
            padx=12,
            pady=6,
        ).pack(fill="x")

        body = tk.Frame(dlg, bg=BG_CARD, padx=14, pady=10)
        body.pack(fill="both", expand=True)

        # Linha 1: Nome da Macro
        r_name = tk.Frame(body, bg=BG_CARD)
        r_name.pack(fill="x", pady=4)
        tk.Label(r_name, text="Macro Name:", bg=BG_CARD, fg=TEXT_WHITE, font=("Arial", 9), width=14, anchor="w").pack(side="left")
        name_ent = tk.Entry(r_name, bg="#203338", fg=TEXT_WHITE, insertbackground=TEXT_WHITE, relief="flat", font=("Arial", 9))
        name_ent.insert(0, f"Macro{len(self.custom_macros) + 1}")
        name_ent.pack(side="left", fill="x", expand=True, ipady=2)

        # Linha 2: Modificadores
        r_mod = tk.Frame(body, bg=BG_CARD)
        r_mod.pack(fill="x", pady=4)
        tk.Label(r_mod, text="Modifiers:", bg=BG_CARD, fg=TEXT_WHITE, font=("Arial", 9), width=14, anchor="w").pack(side="left")
        var_ctrl = tk.BooleanVar(value=False)
        var_shift = tk.BooleanVar(value=False)
        var_alt = tk.BooleanVar(value=False)
        var_super = tk.BooleanVar(value=False)
        for txt, var in (("Ctrl", var_ctrl), ("Shift", var_shift), ("Alt", var_alt), ("Super", var_super)):
            tk.Checkbutton(
                r_mod,
                text=txt,
                variable=var,
                bg=BG_CARD,
                fg=TEXT_WHITE,
                selectcolor="#203338",
                activebackground=BG_CARD,
                activeforeground=TEXT_WHITE,
                font=("Arial", 8),
            ).pack(side="left", padx=4)

        # Linha 3: Captura de Tecla
        r_key = tk.Frame(body, bg=BG_CARD)
        r_key.pack(fill="x", pady=6)
        tk.Label(r_key, text="Key (click & press):", bg=BG_CARD, fg=TEXT_WHITE, font=("Arial", 9), width=14, anchor="w").pack(side="left")
        captured = {"usage": 0x04, "label": "A"}
        key_lbl = tk.Label(
            r_key,
            text="A (Click here and press any key)",
            bg="#203338",
            fg=CYAN_LED,
            font=("Arial", 9, "bold"),
            padx=10,
            pady=4,
            cursor="hand2",
        )
        key_lbl.pack(side="left", fill="x", expand=True)

        def on_key_press(event):
            ks = event.keysym.lower()
            if ks in HID_KEY_USAGES:
                u, lbl = HID_KEY_USAGES[ks]
                captured["usage"] = u
                captured["label"] = lbl
                key_lbl.configure(text=f"Key: {lbl} (HID 0x{u:02X})")

        key_lbl.bind("<Button-1>", lambda _e: key_lbl.focus_set())
        key_lbl.bind("<KeyPress>", on_key_press)
        dlg.bind("<KeyPress>", lambda e: on_key_press(e) if dlg.focus_get() == key_lbl else None)

        # Linha 4: Atribuir diretamente ao Botão (2..5)
        r_assign = tk.Frame(body, bg=BG_CARD)
        r_assign.pack(fill="x", pady=(10, 6))
        tk.Label(r_assign, text="Save & Assign to:", bg=BG_CARD, fg=TEXT_WHITE, font=("Arial", 9), width=14, anchor="w").pack(side="left")

        def save_and_assign(btn_idx: int | None = None):
            m_name = name_ent.get().strip() or f"Key {captured['label']}"
            mod_mask = (
                (0x01 if var_ctrl.get() else 0)
                | (0x02 if var_shift.get() else 0)
                | (0x04 if var_alt.get() else 0)
                | (0x08 if var_super.get() else 0)
            )
            code = config.encode_custom_key_action(mod_mask, captured["usage"])
            self.custom_macros = [m for m in self.custom_macros if m.get("name") != m_name]
            self.custom_macros.append({"name": m_name, "code": code})
            self._save_profiles()
            if btn_idx is not None:
                self._set_button_action(btn_idx, code)
            dlg.destroy()

        for b_num in (2, 3, 4, 5):
            DuiButton(
                r_assign,
                f"Btn {b_num}",
                command=lambda idx=b_num - 1: save_and_assign(idx),
                width=58,
                height=23,
            ).pack(side="left", padx=3)

        # Rodapé: Save Only / Restore Factory Buttons / Cancel
        footer = tk.Frame(dlg, bg=BG_CARD, pady=10)
        footer.pack(fill="x")
        DuiButton(footer, "Save Macro", command=lambda: save_and_assign(None), width=105, height=24).pack(side="left", padx=(14, 6))
        DuiButton(
            footer,
            "Restore Default Buttons & Wheel",
            command=lambda: (self._restore_default_buttons(), dlg.destroy()),
            width=210,
            height=24,
            bg_normal="#0d3b42",
            bg_hover="#135660",
        ).pack(side="left", padx=6)
        DuiButton(footer, "Close", command=dlg.destroy, width=80, height=24).pack(side="right", padx=14)

    def _open_system_mouse_settings(self) -> None:
        if sys.platform == "win32":
            try:
                subprocess.Popen(["control", "main.cpl"], shell=True)
                return
            except Exception:
                pass
        for cmd in (
            ["gnome-control-center", "mouse"],
            ["kcmshell6", "kcm_mouse"],
            ["kcmshell5", "mouse"],
            ["xfce4-mouse-settings"],
            ["cinnamon-settings", "mouse"],
            ["mate-mouse-properties"],
        ):
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except FileNotFoundError:
                continue
        messagebox.showinfo(
            "Mouse Attribute",
            "Could not detect desktop mouse panel automatically.",
            parent=self.root,
        )

    # ------------------------------------------------------------------
    # Comunicação com o Hardware (/dev/hidraw)
    # ------------------------------------------------------------------
    def _call_in_ui(self, fn, *args) -> None:
        """Executa fn na thread do Tk (direto se já estiver nela, senão via fila)."""
        if threading.current_thread() is self._main_thread:
            fn(*args)
        else:
            self._ui_queue.put((fn, args))

    def _pump_ui_queue(self) -> None:
        try:
            for _ in range(200):
                try:
                    fn, args = self._ui_queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    fn(*args)
                except Exception:
                    pass
        finally:
            if getattr(self, "_worker_running", True):
                self.root.after(20, self._pump_ui_queue)

    def _set_status(self, text: str, color: str = "#72efdd") -> None:
        self._call_in_ui(lambda: self.status_label.configure(text=text, fg=color))

    def _open_dev(self) -> hidraw.FeatureDevice | None:
        node = hidraw.find_config_node()
        if node is None:
            self._set_status("X11 receiver (1d57:fa60) not found.", "#fb7185")
            return None
        try:
            return hidraw.FeatureDevice(node)
        except PermissionError:
            self._set_status(f"Permission denied on {node.path} (check udev rules).", "#fb7185")
            return None

    def _ensure_mouse_awake(self, dev: hidraw.FeatureDevice, timeout_s: float = 6.0) -> None:
        """Garante que o mouse 2.4G acordou antes de enviar Feature Reports de escrita."""
        deadline = time.monotonic() + timeout_s
        notified = False
        while True:
            try:
                protocol.read_report(dev, 0x06, 8, 1)
                return
            except protocol.ProtocolError:
                if time.monotonic() >= deadline:
                    raise
                if not notified:
                    notified = True
                    self._set_status("Mouse in 2.4G sleep — move or click mouse to apply...", "#fcd34d")
                time.sleep(0.15)

    def _safe_run(self, fn) -> None:
        try:
            fn()
        except protocol.ProtocolError:
            self._set_status("Mouse in 2.4G sleep mode — move the mouse to wake it up.", "#fcd34d")
        except Exception as exc:
            self._set_status(f"Communication error: {exc}", "#fb7185")

    def _write_reports_async(self, packets: list[bytes], success_msg: str) -> None:
        def worker():
            with self._io_lock:
                dev = self._open_dev()
                if dev is None:
                    return
                with dev:
                    self._ensure_mouse_awake(dev)
                    for pkt in packets:
                        protocol.write_report(dev, pkt)
                        time.sleep(0.03)
                        protocol.write_report(dev, pkt)
            self._set_status(success_msg)

        threading.Thread(target=self._safe_run, args=(worker,), daemon=True).start()

    def sync_from_hardware_async(self) -> None:
        self._set_status("Synchronizing with X11 mouse...", "#72efdd")

        def worker():
            with self._io_lock:
                dev = self._open_dev()
                if dev is None:
                    return
                with dev:
                    raw06 = protocol.read_report(dev, 0x06, 8, 1)
                    raw05 = protocol.read_report(dev, 0x05, 14, 1)
                    raw04 = protocol.read_report(dev, 0x04, 55, 1)
                    self.raw04 = raw04
                    self.raw05 = raw05
                    self.raw06 = raw06

            cfg04 = config.parse_main_config(raw04)
            cfg05 = config.parse_aux_config(raw05)
            hz = config.parse_polling_report(raw06) or 1000

            prof = self.current_profile
            prof["stage_dpis"] = [st.dpi for st in cfg04.stages[:6]]
            prof["stage_colors"] = [list(st.color) for st in cfg04.stages[:6]]
            prof["active_stage"] = max(1, min(6, cfg04.current_stage))
            prof["angle_snap"] = cfg04.angle_snap
            prof["ripple_control"] = cfg04.ripple_control
            prof["polling_hz"] = hz
            prof["light_mode"] = cfg05.light_mode
            prof["light_brightness"] = max(1, min(8, cfg05.light_brightness))
            prof["light_speed"] = max(4, min(8, cfg05.light_speed))
            prof["light_color"] = list(cfg05.light_color)
            prof["sleep_time"] = max(1, min(60, cfg05.sleep_time))
            prof["deep_sleep_time"] = max(1, min(60, cfg05.deep_sleep_time))
            prof["debounce_ms"] = max(2, min(30, cfg05.debounce_ms))
            self._save_profiles()

            active_dpi = prof["stage_dpis"][prof["active_stage"] - 1]
            self._call_in_ui(self._apply_profile_to_widgets, prof)
            conn_str = "USB Cable" if self.battery.cable_present else "Wireless 2.4G"
            bat_str = self.battery.summary()
            self._set_status(
                f"Connected: X11 {conn_str} | Stage {prof['active_stage']} ({active_dpi} DPI) | {hz} Hz | {bat_str}"
            )

        threading.Thread(target=self._safe_run, args=(worker,), daemon=True).start()

    def _log_hid_event(self, text: str) -> None:
        """Registro de diagnóstico (thread do worker): ~/.config/waleattack/hid_events.log."""
        try:
            path = self._event_log_path
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and path.stat().st_size > 512 * 1024:
                path.replace(path.with_suffix(".log.old"))
            with path.open("a", encoding="utf-8") as fh:
                fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}\n")
        except Exception:
            pass

    def _hidraw_monitor_worker(self) -> None:
        """Monitor em thread secundária: nenhuma E/S de sysfs/hidraw roda na thread do Tk."""
        cable_reported: bool | None = None

        def report_cable(present: bool) -> None:
            nonlocal cable_reported
            if present != cable_reported:
                cable_reported = present
                self._log_hid_event(f"CABLE {'CONNECTED' if present else 'REMOVED'}")
                self._call_in_ui(self._on_wired_changed, present)

        # Loop para Windows usando HIDAPI
        if sys.platform == "win32":
            try:
                import hid
            except ImportError:
                hid = None

            open_devs: dict[str, tuple[any, int]] = {}
            last_scan = 0.0

            while getattr(self, "_worker_running", True):
                now = time.monotonic()
                if now - last_scan >= 0.5:
                    last_scan = now
                    try:
                        active = {n.path: n.pid for n in hidraw.find_all_config_nodes()}
                        for path in list(open_devs):
                            if path not in active:
                                d, _ = open_devs.pop(path)
                                try:
                                    d.close()
                                except Exception:
                                    pass
                        if hid is not None:
                            for path, pid in active.items():
                                if path not in open_devs:
                                    try:
                                        d = hid.device()
                                        p = path.encode("utf-8") if isinstance(path, str) else path
                                        d.open_path(p)
                                        d.set_nonblocking(True)
                                        open_devs[path] = (d, pid)
                                    except Exception:
                                        pass
                        report_cable(any(pid != hidraw.DONGLE_PID for pid in active.values()))
                    except Exception:
                        pass

                if not open_devs:
                    time.sleep(0.1)
                    continue

                read_any = False
                for path, (d, pid) in list(open_devs.items()):
                    try:
                        pkt_data = d.read(64, timeout_ms=20)
                        if pkt_data:
                            read_any = True
                            pkt = bytes(pkt_data)
                            if pkt[0] == 0x03:
                                self._log_hid_event(f"{path} pid={pid:04x} {pkt[:8].hex(' ')}")
                            ev = config.parse_input_notification(pkt)
                            if ev:
                                self._call_in_ui(self._handle_input_event, ev, pid != hidraw.DONGLE_PID)
                    except Exception:
                        try:
                            d.close()
                        except Exception:
                            pass
                        open_devs.pop(path, None)
                        last_scan = 0.0

                if not read_any:
                    time.sleep(0.04)

            for d, _ in open_devs.values():
                try:
                    d.close()
                except Exception:
                    pass
            open_devs.clear()
            return

        # Loop para Linux usando /dev/hidraw e select
        open_fds: dict[str, tuple[int, int]] = {}  # path -> (fd, pid)
        last_scan = 0.0

        while getattr(self, "_worker_running", True):
            now = time.monotonic()

            # Varredura de hotplug a cada 0.5s
            if now - last_scan >= 0.5:
                last_scan = now
                try:
                    active = {n.path: n.pid for n in hidraw.find_all_config_nodes()}
                    for path in list(open_fds):
                        if path not in active:
                            fd, _pid = open_fds.pop(path)
                            try:
                                os.close(fd)
                            except OSError:
                                pass
                    for path, pid in active.items():
                        if path not in open_fds:
                            try:
                                open_fds[path] = (os.open(path, os.O_RDONLY | os.O_NONBLOCK), pid)
                            except OSError:
                                pass
                    report_cable(any(pid != hidraw.DONGLE_PID for pid in active.values()))
                except Exception:
                    pass

            if not open_fds:
                time.sleep(0.1)
                continue

            try:
                readable, _, _ = select.select([fd for fd, _ in open_fds.values()], [], [], 0.1)
            except (ValueError, OSError):
                time.sleep(0.05)
                continue

            for path, (fd, pid) in list(open_fds.items()):
                if fd not in readable:
                    continue
                while True:
                    try:
                        pkt = os.read(fd, 64)
                    except BlockingIOError:
                        break
                    except OSError:
                        # nó removido (cabo desconectado): fecha já e força nova varredura
                        try:
                            os.close(fd)
                        except OSError:
                            pass
                        open_fds.pop(path, None)
                        last_scan = 0.0
                        break
                    if not pkt:
                        break
                    if pkt[0] == 0x03:
                        self._log_hid_event(f"{path} pid={pid:04x} {pkt[:8].hex(' ')}")
                    ev = config.parse_input_notification(pkt)
                    if ev:
                        self._call_in_ui(self._handle_input_event, ev, pid != hidraw.DONGLE_PID)

        for fd, _ in open_fds.values():
            try:
                os.close(fd)
            except OSError:
                pass
        open_fds.clear()

    def _status_line(self) -> str:
        prof = self.current_profile
        active_stage = int(prof.get("active_stage", 2))
        dpis = prof.get("stage_dpis", [800, 1600, 2400, 3200, 5000, 22000])
        active_dpi = dpis[active_stage - 1] if 1 <= active_stage <= len(dpis) else 1600
        hz = int(prof.get("polling_hz", 1000))
        conn_str = "USB Cable" if self.battery.cable_present else "Wireless 2.4G"
        return (
            f"Connected: X11 {conn_str} | Stage {active_stage} ({active_dpi} DPI) | {hz} Hz | "
            f"{self.battery.summary()}"
        )

    def _refresh_battery_ui(self, *, center: bool = False) -> None:
        self._draw_battery()
        if center:
            self._draw_center_canvas()
        self._set_status(self._status_line())

    def _on_wired_changed(self, wired_now: bool) -> None:
        """Thread do Tk: interface do cabo USB apareceu/sumiu."""
        if self.battery.on_cable(wired_now):
            self._charge_anim_step = 0
            self._refresh_battery_ui(center=True)

    def _handle_input_event(self, ev: dict, from_wired: bool = False) -> None:
        kind = ev.get("type")
        if kind == "battery":
            prev_level = self.battery.level
            prev_mode = self.battery.mode
            changed = self.battery.on_report(int(ev.get("status", 0)), ev.get("percent"), from_wired)
            if self.battery.level != prev_level:
                self._save_profiles()
            if changed:
                self._refresh_battery_ui(center=(self.battery.mode != prev_mode))
        elif kind == "stage":
            st = max(1, min(6, int(ev["stage"])))
            self.current_profile["active_stage"] = st
            for i, dot in enumerate(self.dpi_dots):
                dot.set_selected((i + 1) == st)
            dpi = self.current_profile["stage_dpis"][st - 1]
            self._set_status(f"DPI Button -> Stage {st} ({dpi} DPI)")
        elif kind == "polling":
            hz = int(ev["hz"])
            self.current_profile["polling_hz"] = hz
            for h, dot in self.polling_dots.items():
                dot.set_selected(h == hz)

    def _on_close(self) -> None:
        self._worker_running = False
        self._save_profiles()
        self.root.destroy()


def main() -> int:
    root = tk.Tk(className="waleattack")
    WaleAttackApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
