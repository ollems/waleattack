"""Máquina de estados da bateria do X11 (sem Tkinter, testável).

Semântica do Input Report 0x03 0x55 0x40 <b3> <b4>, conforme o driver original
(cms4.asm 0x4a1782..0x4a189b) e capturas reais em /dev/hidraw:

* Interface do cabo USB (PID fa55):
    - b3 == 2  -> carga completa (100 %).
    - b3 != 2  -> carregando. **b4 é um placeholder (sempre 0x64 = 100)** e o
      driver original nunca o lê. NÃO é o nível real.
* Interface do dongle 2.4G (PID fa60):
    - b3 == 3  -> carregando por carregador/base externa (b4 também ignorado).
    - b3 != 3  -> em uso na bateria; b4 (1..100) é o nível REAL.

Durante a carga o firmware não informa o nível; por isso guardamos o último
nível medido e, ao remover o cabo, marcamos o valor como desatualizado até a
próxima leitura real do dongle.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

MODE_UNKNOWN = "unknown"
MODE_DISCHARGING = "discharging"
MODE_CHARGING_CABLE = "charging_cable"
MODE_CHARGING_DOCK = "charging_dock"
MODE_FULL = "full"

CHARGING_MODES = (MODE_CHARGING_CABLE, MODE_CHARGING_DOCK)


@dataclass
class BatteryState:
    level: int | None = None          # último nível REAL medido (1..100)
    level_wall_ts: float = 0.0        # time.time() da última medição real
    stale: bool = True                # nível desatualizado (ainda sem leitura nova)
    mode: str = MODE_UNKNOWN
    cable_present: bool = False
    charge_started_mono: float = 0.0  # time.monotonic() do início da carga
    last_packet_mono: float = 0.0
    _listeners: list = field(default_factory=list, repr=False)

    # ------------------------------------------------------------------
    @property
    def is_charging(self) -> bool:
        return self.mode in CHARGING_MODES

    @property
    def is_full(self) -> bool:
        return self.mode == MODE_FULL

    @property
    def is_dock(self) -> bool:
        return self.mode == MODE_CHARGING_DOCK

    @property
    def waiting_reading(self) -> bool:
        """Em uso na bateria, mas o nível exibido ainda é antigo (pós-carga/inicialização)."""
        return self.mode in (MODE_DISCHARGING, MODE_UNKNOWN) and (self.stale or self.level is None)

    # ------------------------------------------------------------------
    def restore(self, level: int | None, wall_ts: float = 0.0) -> None:
        """Restaura o último nível salvo em disco (sempre como desatualizado)."""
        if isinstance(level, int) and 1 <= level <= 100:
            self.level = level
            self.level_wall_ts = float(wall_ts or 0.0)
        self.stale = True

    def _start_charging(self, mode: str, now: float) -> None:
        if self.mode not in CHARGING_MODES:
            self.charge_started_mono = now
        self.mode = mode

    def on_cable(self, present: bool, now: float | None = None) -> bool:
        """Interface do cabo USB apareceu/sumiu. Retorna True se o estado mudou."""
        now = time.monotonic() if now is None else now
        if present == self.cable_present:
            return False
        self.cable_present = present
        if present:
            if self.mode != MODE_FULL:
                self._start_charging(MODE_CHARGING_CABLE, now)
        else:
            was_charging = self.mode in CHARGING_MODES or self.mode == MODE_FULL
            self.mode = MODE_DISCHARGING
            if was_charging:
                # o nível medido antes da carga não vale mais
                self.stale = True
        return True

    def on_report(self, b3: int, b4: int | None, from_cable: bool, now: float | None = None) -> bool:
        """Processa um report 0x40. Retorna True se algo visível mudou."""
        now = time.monotonic() if now is None else now
        self.last_packet_mono = now
        before = (self.mode, self.level, self.stale, self.cable_present)

        if from_cable:
            self.cable_present = True
            if b3 == 2:
                self.mode = MODE_FULL
                self._set_level(100)
            else:
                self._start_charging(MODE_CHARGING_CABLE, now)
        else:
            if b3 == 3:
                self._start_charging(MODE_CHARGING_DOCK, now)
            elif self.cable_present:
                # pacote atrasado do dongle com o cabo ainda conectado: a interface do cabo manda
                pass
            else:
                if self.mode in CHARGING_MODES or self.mode == MODE_FULL:
                    self.stale = True
                self.mode = MODE_DISCHARGING
                if b4 is not None and 1 <= b4 <= 100:
                    self._set_level(b4)

        return before != (self.mode, self.level, self.stale, self.cable_present)

    def _set_level(self, value: int) -> None:
        self.level = int(value)
        self.level_wall_ts = time.time()
        self.stale = False

    # ------------------------------------------------------------------
    def charge_elapsed_s(self, now: float | None = None) -> float:
        if not self.is_charging or not self.charge_started_mono:
            return 0.0
        now = time.monotonic() if now is None else now
        return max(0.0, now - self.charge_started_mono)

    def summary(self) -> str:
        """Texto curto para a barra de status."""
        lvl = f"{self.level}%" if self.level is not None else "--%"
        if self.is_full:
            return "Bateria: 100% (carga completa)"
        if self.mode == MODE_CHARGING_CABLE:
            return f"⚡ Carregando via cabo USB (último nível medido: {lvl})"
        if self.mode == MODE_CHARGING_DOCK:
            return f"⚡ Carregando na base/carregador (último nível medido: {lvl})"
        if self.waiting_reading:
            return f"Bateria: {lvl} (aguardando leitura atualizada do mouse)"
        return f"Bateria: {lvl}"
