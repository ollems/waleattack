"""Camada de protocolo HID (classe CMS_4 / protocolo vendor 0xA0).

Sequência de handshake e comunicação:
* select_report(report_id, length, flag): handshake via report 0xA0
* write_report(buf): envio com até 5 tentativas + delay de estabilização
* construtor do report 0x04 (DPI / estágios / cores)
* sequência de conexão (dongle 2.4G e cabo USB):
    0x0b (8 B, flag 0): identificação do modelo
    0x06 (9 B, flag 1): polling rate (125, 250, 500, 1000 Hz)
    0x05 (15 B, flag 1): iluminação RGB, debounce, timers
    0x04 (56 B, flag 1): configuração principal de DPI, sensores e cores
"""
from __future__ import annotations

import time

from .hidraw import FeatureDevice

REPORT_SELECT = 0xA0  # report de controle: "quero ler o report X com N bytes"
SELECT_LEN = 8  # tamanho total (com report id) no fio


class ProtocolError(RuntimeError):
    pass


def select_report(dev: FeatureDevice, report_id: int, length: int, flag: int = 0,
                  retries: int = 10, delay: float = 0.1) -> bool:
    """Equivalente a 0x4a3f50 (versão feature/dongle, flag [esi+0x3dc]==1).

    Envia A0 [report_id, length, 0, flag] e confere o ack (byte 1 == 1).
    `length` é o tamanho total do report com o byte de id (ex.: 8 para 0x0b).
    """
    req = bytes([REPORT_SELECT, report_id, length, 0, flag, 0, 0, 0])
    for _ in range(retries):
        try:
            dev.set_feature(req)
            break
        except OSError:
            time.sleep(delay)
    else:
        raise ProtocolError("falha ao enviar o select (A0)")
    time.sleep(delay)
    ack = dev.get_feature(REPORT_SELECT, SELECT_LEN - 1)
    return ack[1] == 1


def read_report(dev: FeatureDevice, report_id: int, payload_len: int, flag: int = 1,
                attempts: int = 5, delay: float = 0.1) -> bytes:
    """Lê um report de configuração: select (A0) + GetFeature(report_id).

    Retorna report_id + payload (payload_len + 1 bytes).
    `flag` é 0 para o report 0x0b e 1 para 0x06/0x05/0x04, como no app original.
    O app original tenta até 5 vezes (0x4a3b1d / 0x4a3c0d) antes de desistir.
    """
    last = b""
    for _ in range(attempts):
        if select_report(dev, report_id, payload_len + 1, flag):
            data = dev.get_feature(report_id, payload_len)
            if data[0] == report_id and data[1] == payload_len + 1:
                return data
            last = data
        time.sleep(delay)
    raise ProtocolError(f"sem resposta válida do report 0x{report_id:02x}" +
                        (f"; último dado: {last.hex(' ')}" if last else ""))


def write_report(dev: FeatureDevice, data: bytes, attempts: int = 5, delay: float = 0.2) -> None:
    """Equivalente a 0x4a1970 (caminho padrão para reports != 0x09, [esi+0x3dc]==1).

    Tenta SetFeature(data) até `attempts` vezes, aguardando 200 ms após cada tentativa.
    """
    if not data or data[0] == 0x09:
        raise ValueError("write_report padrão não suporta report vazio ou 0x09 fatiado")
    last_exc: OSError | None = None
    for _ in range(attempts):
        try:
            dev.set_feature(data)
            time.sleep(delay)
            return
        except OSError as exc:
            last_exc = exc
            time.sleep(delay)
    raise ProtocolError(f"falha ao gravar report 0x{data[0]:02x}: {last_exc}")


def read_identity(dev: FeatureDevice) -> dict[str, bytes]:
    """Reports usados pelo app logo após conectar (0x4a3980 e 0x4a3a1b)."""
    return {
        "0x0b": read_report(dev, 0x0B, 7, flag=0),
        "0x06": read_report(dev, 0x06, 8, flag=1),
    }
