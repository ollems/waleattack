"""Acesso ao hidraw (Linux) e HIDAPI (Windows) para os Feature Reports do hardware WaleAttack.

No Windows o app usa HidD_SetFeature/HidD_GetFeature via hidapi. No Linux o equivalente
são os ioctls HIDIOCSFEATURE/HIDIOCGFEATURE sobre /dev/hidrawN.
"""
from __future__ import annotations

import glob
import os
import sys
from dataclasses import dataclass, field

if sys.platform != "win32":
    import fcntl
else:
    try:
        import hid
    except ImportError:
        hid = None

VENDOR_ID = 0x1D57
DONGLE_PID = 0xFA60  # receptor 2.4G "Xenta", comum a todos os modelos
WIRED_PID = 0xFA55   # cabo USB direto no mouse (VID 1d57:fa55)


_IOC_WRITE = 1
_IOC_READ = 2


def _ioc(direction: int, typ: str, nr: int, size: int) -> int:
    return (direction << 30) | (size << 16) | (ord(typ) << 8) | nr


def HIDIOCSFEATURE(length: int) -> int:
    return _ioc(_IOC_WRITE | _IOC_READ, "H", 0x06, length)


def HIDIOCGFEATURE(length: int) -> int:
    return _ioc(_IOC_WRITE | _IOC_READ, "H", 0x07, length)


@dataclass
class ReportDescriptorInfo:
    """Tamanhos (em bytes, sem o byte de report id) dos feature reports."""

    feature: dict[int, int] = field(default_factory=dict)
    input: dict[int, int] = field(default_factory=dict)
    output: dict[int, int] = field(default_factory=dict)


def parse_report_descriptor(desc: bytes) -> ReportDescriptorInfo:
    """Parser mínimo: só acompanha Report ID/Size/Count e os itens Main."""
    info = ReportDescriptorInfo()
    report_id = 0
    size = count = 0
    i = 0
    while i < len(desc):
        prefix = desc[i]
        if prefix == 0xFE:  # long item
            i += 3 + desc[i + 1]
            continue
        sz = prefix & 0x03
        sz = 4 if sz == 3 else sz
        typ = (prefix >> 2) & 0x03
        tag = prefix >> 4
        data = int.from_bytes(desc[i + 1 : i + 1 + sz], "little")
        if typ == 1:  # Global
            if tag == 7:
                size = data
            elif tag == 8:
                report_id = data
            elif tag == 9:
                count = data
        elif typ == 0:  # Main
            bits = size * count
            target = {8: info.input, 9: info.output, 11: info.feature}.get(tag)
            if target is not None:
                target[report_id] = target.get(report_id, 0) + bits // 8
        i += 1 + sz
    return info


@dataclass
class HidrawNode:
    path: str
    vid: int
    pid: int
    name: str
    descriptor: ReportDescriptorInfo

    @property
    def has_config_reports(self) -> bool:
        return bool(self.descriptor.feature)


def _read(path: str) -> bytes | None:
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def enumerate_nodes(vid: int = VENDOR_ID, load_descriptors: bool = True) -> list[HidrawNode]:
    nodes: list[HidrawNode] = []

    # Implementação Windows via HIDAPI
    if sys.platform == "win32":
        if hid is None:
            return []
        try:
            dev_list = hid.enumerate(vid, 0)
        except Exception:
            return []
        for d in dev_list:
            raw_path = d.get("path")
            if not raw_path:
                continue
            path_str = raw_path.decode("utf-8", errors="replace") if isinstance(raw_path, bytes) else str(raw_path)
            nvid = d.get("vendor_id", vid)
            npid = d.get("product_id", 0)
            name = d.get("product_string") or "WaleAttack Gaming Mouse"
            usage_page = d.get("usage_page", 0)
            interface_number = d.get("interface_number", -1)

            desc_info: ReportDescriptorInfo | None = None
            if load_descriptors:
                try:
                    dev = hid.device()
                    dev.open_path(raw_path if isinstance(raw_path, bytes) else raw_path.encode("utf-8"))
                    raw_desc = dev.get_report_descriptor()
                    dev.close()
                    if raw_desc:
                        desc_info = parse_report_descriptor(bytes(raw_desc))
                except Exception:
                    pass

            if desc_info is None:
                # Heurística para interface de configuração no Windows
                is_cfg = (usage_page >= 0xFF00) or (interface_number >= 1) or (usage_page != 1)
                if is_cfg:
                    desc_info = ReportDescriptorInfo(
                        feature={0x04: 55, 0x05: 14, 0x06: 8, 0x08: 15, 0x0B: 7, 0xA0: 7},
                        input={3: 7},
                    )
                else:
                    desc_info = ReportDescriptorInfo({}, {})

            nodes.append(
                HidrawNode(
                    path=path_str,
                    vid=nvid,
                    pid=npid,
                    name=name,
                    descriptor=desc_info,
                )
            )
        return nodes

    # Implementação Linux via /sys/class/hidraw
    try:
        sys_paths = sorted(glob.glob("/sys/class/hidraw/hidraw*"))
    except OSError:
        return []

    for sys_dir in sys_paths:
        try:
            dev = os.path.join(sys_dir, "device")
            uevent_bytes = _read(os.path.join(dev, "uevent"))
            if not uevent_bytes:
                continue
            uevent = uevent_bytes.decode(errors="replace")
            hid_id = next((l for l in uevent.splitlines() if l.startswith("HID_ID=")), None)
            if not hid_id or "=" not in hid_id:
                continue
            parts = hid_id.split("=", 1)[1].strip().split(":")
            if len(parts) < 3:
                continue
            nvid, npid = int(parts[1], 16), int(parts[2], 16)
            if nvid != vid:
                continue
            name_line = next((l for l in uevent.splitlines() if l.startswith("HID_NAME=")), "")
            name = name_line.split("=", 1)[1] if "=" in name_line else ""
            if load_descriptors:
                desc = _read(os.path.join(dev, "report_descriptor")) or b""
                parsed_desc = parse_report_descriptor(desc)
            else:
                parsed_desc = ReportDescriptorInfo({}, {})
            nodes.append(
                HidrawNode(
                    path="/dev/" + os.path.basename(sys_dir),
                    vid=nvid,
                    pid=npid,
                    name=name,
                    descriptor=parsed_desc,
                )
            )
        except Exception:
            continue
    return nodes


def find_all_config_nodes(vid: int = VENDOR_ID) -> list[HidrawNode]:
    """Todas as interfaces (cabo e dongle 2.4G) que expõem feature reports ou input 0x03."""
    try:
        return [
            n
            for n in enumerate_nodes(vid)
            if n.has_config_reports or 3 in n.descriptor.input
        ]
    except Exception:
        return []


def is_wired_connected(vid: int = VENDOR_ID) -> bool:
    """Retorna True se o mouse estiver conectado via cabo USB (PID != 0xfa60, ex.: 0xfa55)."""
    try:
        return any(n.pid != DONGLE_PID for n in enumerate_nodes(vid, load_descriptors=False))
    except Exception:
        return False


def find_config_node(vid: int = VENDOR_ID) -> HidrawNode | None:
    """Interface que expõe os feature reports de configuração (prioriza cabo USB se conectado)."""
    try:
        cfg_nodes = [n for n in enumerate_nodes(vid) if n.has_config_reports]
        for n in cfg_nodes:
            if n.pid != DONGLE_PID:
                return n
        return cfg_nodes[0] if cfg_nodes else None
    except Exception:
        return None


class FeatureDevice:
    """Equivalente de Open_FeatureDevice/GetFeature/SetFeature do hiddriver_N.dll."""

    def __init__(self, node: HidrawNode):
        self.node = node
        self.fd: int = -1
        self._dev = None

        if sys.platform == "win32":
            if hid is not None:
                self._dev = hid.device()
                path = self.node.path
                if isinstance(path, str):
                    path = path.encode("utf-8")
                self._dev.open_path(path)
        else:
            self.fd = os.open(node.path, os.O_RDWR)

    def close(self) -> None:
        if self._dev is not None:
            try:
                self._dev.close()
            except Exception:
                pass
            self._dev = None
        if self.fd >= 0:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = -1

    def __enter__(self) -> "FeatureDevice":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def get_feature(self, report_id: int, payload_len: int) -> bytes:
        """Devolve report_id + payload (len = payload_len + 1), como o GetFeature do Windows."""
        if self._dev is not None:
            resp = self._dev.get_feature_report(report_id, payload_len + 1)
            return bytes(resp)
        buf = bytearray(payload_len + 1)
        buf[0] = report_id
        fcntl.ioctl(self.fd, HIDIOCGFEATURE(len(buf)), buf, True)
        return bytes(buf)

    def set_feature(self, data: bytes) -> None:
        """data[0] é o report id."""
        if self._dev is not None:
            self._dev.send_feature_report(data)
            return
        buf = bytearray(data)
        fcntl.ioctl(self.fd, HIDIOCSFEATURE(len(buf)), buf, True)
