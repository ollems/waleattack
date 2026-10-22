"""CLI do WaleAttack para Linux e Windows."""
from __future__ import annotations

import argparse
import sys
import time

from . import config, hidraw, protocol


def _open_device_or_exit() -> hidraw.FeatureDevice:
    node = hidraw.find_config_node()
    if node is None:
        print("Interface de configuração não encontrada.", file=sys.stderr)
        raise SystemExit(1)
    try:
        return hidraw.FeatureDevice(node)
    except PermissionError:
        print(
            f"Sem permissão em {node.path}. Instale a regra udev "
            "(udev/70-waleattack.rules) ou rode com sudo.",
            file=sys.stderr,
        )
        raise SystemExit(2)


def _read_with_wake(dev: hidraw.FeatureDevice, report_id: int, payload_len: int,
                    flag: int = 1, wait_seconds: float = 0.0) -> bytes:
    deadline = time.time() + wait_seconds
    announced = False
    while True:
        try:
            return protocol.read_report(dev, report_id, payload_len, flag)
        except protocol.ProtocolError:
            if time.time() >= deadline:
                print(
                    "Mouse não respondeu (provavelmente em modo sleep 2.4G ou desligado).\n"
                    "Mova o mouse para acordá-lo ou use --wait 15.",
                    file=sys.stderr,
                )
                raise SystemExit(4)
            if not announced:
                print("Aguardando o mouse acordar (mova o mouse)...", file=sys.stderr, flush=True)
                announced = True
            time.sleep(0.25)


def cmd_list(_args) -> int:
    nodes = hidraw.enumerate_nodes()
    if not nodes:
        print("Nenhum dispositivo 1d57:* encontrado.", file=sys.stderr)
        return 1
    for n in nodes:
        mark = "  <- configuração" if n.has_config_reports else ""
        print(f"{n.path}  {n.vid:04x}:{n.pid:04x}  {n.name}{mark}")
        if n.has_config_reports:
            for rid, size in sorted(n.descriptor.feature.items()):
                print(f"    feature 0x{rid:02x}: {size} bytes")
    return 0


def cmd_dump(args) -> int:
    dev = _open_device_or_exit()
    wanted = {int(x, 16) for x in args.ids} if args.ids else None
    with dev:
        for rid, size in sorted(dev.node.descriptor.feature.items()):
            if wanted is not None and rid not in wanted:
                continue
            try:
                data = dev.get_feature(rid, size)
                print(f"0x{rid:02x} [{size:3d}] {data.hex(' ')}")
            except OSError as exc:
                print(f"0x{rid:02x} [{size:3d}] erro: {exc}")
    return 0


def cmd_probe(args) -> int:
    dev = _open_device_or_exit()
    with dev:
        for name, rid, n, flag in (("0x0b", 0x0B, 7, 0), ("0x06", 0x06, 8, 1),
                                   ("0x05", 0x05, 14, 1), ("0x04", 0x04, 55, 1)):
            data = _read_with_wake(dev, rid, n, flag, args.wait)
            print(f"{name}: {data.hex(' ')}")
    return 0


def cmd_watch(args) -> int:
    """Lê os reports repetidamente e mostra só os bytes que mudaram (somente leitura)."""
    dev = _open_device_or_exit()
    spec = (("0x06", 0x06, 8), ("0x05", 0x05, 14), ("0x04", 0x04, 55))
    last: dict[str, bytes] = {}
    end = time.time() + args.seconds
    print(f"Observando por {args.seconds}s. Aperte os botões do mouse (DPI, etc.)...", flush=True)
    with dev:
        while time.time() < end:
            for name, rid, n in spec:
                try:
                    data = protocol.read_report(dev, rid, n, 1, attempts=2, delay=0.05)
                except (protocol.ProtocolError, OSError):
                    continue
                old = last.get(name)
                if old is None:
                    print(f"[{time.strftime('%H:%M:%S')}] {name} inicial: {data.hex(' ')}", flush=True)
                elif old != data:
                    diff = ", ".join(f"[{i}] {a:02x}->{b:02x}" for i, (a, b) in enumerate(zip(old, data)) if a != b)
                    print(f"[{time.strftime('%H:%M:%S')}] {name} mudou: {diff}", flush=True)
                last[name] = data
            time.sleep(args.interval)
    return 0


def cmd_show(args) -> int:
    dev = _open_device_or_exit()
    with dev:
        raw04 = _read_with_wake(dev, 0x04, 55, 1, args.wait)
        raw06 = _read_with_wake(dev, 0x06, 8, 1, args.wait)
        raw05 = _read_with_wake(dev, 0x05, 14, 1, args.wait)
    cfg = config.parse_main_config(raw04)
    hz = config.parse_polling_report(raw06)
    aux = config.parse_aux_config(raw05)

    print(f"Polling rate: {hz if hz else '?'} Hz")
    print(f"Debounce:     {aux.debounce_ms} ms")
    print(f"Angle Snap:   {'on' if cfg.angle_snap else 'off'}   Ripple Control: {'on' if cfg.ripple_control else 'off'}")
    lr, lg, lb = aux.light_color
    print(
        f"Iluminação:   modo={aux.light_mode}  brilho={aux.light_brightness}/8  "
        f"velocidade={aux.light_speed}/8  cor=#{lr:02x}{lg:02x}{lb:02x}"
    )
    print(f"Sleep:        light_off={aux.sleep_time}  deep_sleep={aux.deep_sleep_time}")
    print(f"Estágios DPI (checksum {'ok' if cfg.checksum_ok else 'INVÁLIDO'}, atual={cfg.current_stage}):")
    for st in cfg.stages:
        if not st.enabled:
            continue
        mark = "  <- atual" if st.number == cfg.current_stage else ""
        r, g, b = st.color
        print(f"  estágio {st.number}: {st.dpi:>6} DPI   cor #{r:02x}{g:02x}{b:02x}{mark}")
    return 0


def cmd_set_dpi(args) -> int:
    dev = _open_device_or_exit()
    with dev:
        before = _read_with_wake(dev, 0x04, 55, 1, args.wait)
        updated = config.update_stage_dpi(before, args.stage, args.dpi)
        protocol.write_report(dev, updated)
        after = _read_with_wake(dev, 0x04, 55, 1, args.wait)
    cfg = config.parse_main_config(after)
    st = cfg.stages[args.stage - 1]
    print(
        f"Estágio {st.number} atualizado -> lido do mouse: {st.dpi} DPI "
        f"(code=0x{st.code:02x}, checksum={'ok' if cfg.checksum_ok else 'ERRO'})"
    )
    return 0 if st.dpi == args.dpi and cfg.checksum_ok else 3


def cmd_set_stage(args) -> int:
    dev = _open_device_or_exit()
    with dev:
        before = _read_with_wake(dev, 0x04, 55, 1, args.wait)
        updated = config.update_active_stage(before, args.stage)
        protocol.write_report(dev, updated)
        after = _read_with_wake(dev, 0x04, 55, 1, args.wait)
    cfg = config.parse_main_config(after)
    print(f"Estágio ativo atualizado -> lido do mouse: {cfg.current_stage} ({cfg.stages[cfg.current_stage - 1].dpi} DPI)")
    return 0 if cfg.current_stage == args.stage and cfg.checksum_ok else 3


def cmd_set_stage_color(args) -> int:
    rgb = config.parse_hex_color(args.color)
    dev = _open_device_or_exit()
    with dev:
        before = _read_with_wake(dev, 0x04, 55, 1, args.wait)
        updated = config.update_stage_color(before, args.stage, rgb)
        protocol.write_report(dev, updated)
        after = _read_with_wake(dev, 0x04, 55, 1, args.wait)
    cfg = config.parse_main_config(after)
    r, g, b = cfg.stages[args.stage - 1].color
    print(f"Cor do estágio {args.stage} atualizada -> #{r:02x}{g:02x}{b:02x}")
    return 0 if (r, g, b) == rgb and cfg.checksum_ok else 3


def cmd_set_sensor(args) -> int:
    if args.angle_snap is None and args.ripple_control is None:
        print("Especifique --angle-snap e/ou --ripple-control (on|off).", file=sys.stderr)
        return 2
    dev = _open_device_or_exit()
    with dev:
        before = _read_with_wake(dev, 0x04, 55, 1, args.wait)
        updated = config.update_sensor_flags(
            before,
            angle_snap=(args.angle_snap == "on") if args.angle_snap else None,
            ripple_control=(args.ripple_control == "on") if args.ripple_control else None,
        )
        protocol.write_report(dev, updated)
        after = _read_with_wake(dev, 0x04, 55, 1, args.wait)
    cfg = config.parse_main_config(after)
    print(f"Sensor atualizado -> Angle Snap={'on' if cfg.angle_snap else 'off'}, Ripple Control={'on' if cfg.ripple_control else 'off'}")
    return 0


def cmd_reset_dpi(args) -> int:
    dev = _open_device_or_exit()
    with dev:
        before = _read_with_wake(dev, 0x04, 55, 1, args.wait)
        updated = config.reset_dpi_stages(before)
        protocol.write_report(dev, updated)
        after = _read_with_wake(dev, 0x04, 55, 1, args.wait)
    cfg = config.parse_main_config(after)
    print(f"Estágios DPI restaurados para o padrão de fábrica (checksum={'ok' if cfg.checksum_ok else 'ERRO'}).")
    return 0 if cfg.checksum_ok else 3


def cmd_reset_buttons(args) -> int:
    dev = _open_device_or_exit()
    pkt = config.build_button_report([0x01, 0x02, 0x03, 0x04, 0x05])
    with dev:
        _read_with_wake(dev, 0x06, 8, 1, args.wait)
        protocol.write_report(dev, pkt)
    print("Botões 1..5 restaurados para o padrão de fábrica (Left, Right, Middle, Forward, Backward).")
    return 0


def cmd_set_polling(args) -> int:
    dev = _open_device_or_exit()
    pkt = config.build_polling_report(args.hz)
    with dev:
        _read_with_wake(dev, 0x06, 8, 1, args.wait)
        protocol.write_report(dev, pkt)
        after = _read_with_wake(dev, 0x06, 8, 1, args.wait)
    hz = config.parse_polling_report(after)
    print(f"Polling rate atualizado -> lido do mouse: {hz} Hz")
    return 0 if hz == args.hz else 3


def cmd_set_debounce(args) -> int:
    dev = _open_device_or_exit()
    with dev:
        before = _read_with_wake(dev, 0x05, 14, 1, args.wait)
        updated = config.update_aux_config(before, debounce_ms=args.ms)
        protocol.write_report(dev, updated)
        after = _read_with_wake(dev, 0x05, 14, 1, args.wait)
    aux = config.parse_aux_config(after)
    print(f"Debounce atualizado -> lido do mouse: {aux.debounce_ms} ms (checksum={'ok' if aux.checksum_ok else 'ERRO'})")
    return 0 if aux.debounce_ms == args.ms and aux.checksum_ok else 3


def cmd_set_light(args) -> int:
    rgb = config.parse_hex_color(args.color) if args.color else None
    dev = _open_device_or_exit()
    with dev:
        before = _read_with_wake(dev, 0x05, 14, 1, args.wait)
        updated = config.update_aux_config(
            before,
            light_mode=args.mode,
            light_brightness=args.brightness,
            light_speed=args.speed,
            light_color=rgb,
        )
        protocol.write_report(dev, updated)
        after = _read_with_wake(dev, 0x05, 14, 1, args.wait)
    aux = config.parse_aux_config(after)
    lr, lg, lb = aux.light_color
    print(
        f"Iluminação atualizada -> modo={aux.light_mode} brilho={aux.light_brightness}/8 "
        f"velocidade={aux.light_speed}/8 cor=#{lr:02x}{lg:02x}{lb:02x}"
    )
    return 0 if aux.checksum_ok else 3


def cmd_gui(_args) -> int:
    from .gui import main as gui_main
    return gui_main()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="waleattack-cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("gui", help="abre a interface gráfica WaleAttack").set_defaults(func=cmd_gui)
    sub.add_parser("list", help="lista interfaces hidraw compatíveis").set_defaults(func=cmd_list)

    d = sub.add_parser("dump", help="lê (GET) os feature reports")
    d.add_argument("ids", nargs="*", help="report ids em hex (padrão: todos)")
    d.set_defaults(func=cmd_dump)

    sh = sub.add_parser("show", help="mostra DPI, polling rate, iluminação, debounce e sensores")
    sh.add_argument("--wait", type=float, default=0.0, help="segundos para aguardar o mouse acordar")
    sh.set_defaults(func=cmd_show)

    sd = sub.add_parser("set-dpi", help="altera o DPI de um estágio (1..8)")
    sd.add_argument("stage", type=int, help="número do estágio (1..8)")
    sd.add_argument("dpi", type=int, help="novo valor de DPI (50..22000)")
    sd.add_argument("--wait", type=float, default=0.0, help="segundos para aguardar o mouse acordar")
    sd.set_defaults(func=cmd_set_dpi)

    ss = sub.add_parser("set-stage", help="seleciona o estágio de DPI ativo (1..8)")
    ss.add_argument("stage", type=int, help="número do estágio ativo (1..8)")
    ss.add_argument("--wait", type=float, default=0.0)
    ss.set_defaults(func=cmd_set_stage)

    sc = sub.add_parser("set-stage-color", help="altera a cor RGB de um estágio de DPI")
    sc.add_argument("stage", type=int, help="número do estágio (1..8)")
    sc.add_argument("color", help="cor em hex (ex: ff0000)")
    sc.add_argument("--wait", type=float, default=0.0)
    sc.set_defaults(func=cmd_set_stage_color)

    sn = sub.add_parser("set-sensor", help="ativa/desativa Angle Snap e Ripple Control")
    sn.add_argument("--angle-snap", choices=("on", "off"))
    sn.add_argument("--ripple-control", choices=("on", "off"))
    sn.add_argument("--wait", type=float, default=0.0)
    sn.set_defaults(func=cmd_set_sensor)

    rd = sub.add_parser("reset-dpi", help="restaura os estágios de DPI padrão (800/1600/2400/3200/5000/22000)")
    rd.add_argument("--wait", type=float, default=0.0)
    rd.set_defaults(func=cmd_reset_dpi)

    rb = sub.add_parser("reset-buttons", help="restaura os botões 1..5 para o padrão de fábrica")
    rb.add_argument("--wait", type=float, default=0.0)
    rb.set_defaults(func=cmd_reset_buttons)

    sp = sub.add_parser("set-polling", help="altera o polling rate (125, 250, 500, 1000)")
    sp.add_argument("hz", type=int, choices=(125, 250, 500, 1000))
    sp.add_argument("--wait", type=float, default=0.0, help="segundos para aguardar o mouse acordar")
    sp.set_defaults(func=cmd_set_polling)

    db = sub.add_parser("set-debounce", help="altera o key debounce time em ms (par, 2..30)")
    db.add_argument("ms", type=int, help="tempo em ms (ex: 4, 8)")
    db.add_argument("--wait", type=float, default=0.0)
    db.set_defaults(func=cmd_set_debounce)

    lg = sub.add_parser("set-light", help="configura iluminação (report 0x05)")
    lg.add_argument("--mode", type=int, choices=range(0, 7))
    lg.add_argument("--brightness", type=int, choices=range(1, 9))
    lg.add_argument("--speed", type=int, choices=range(4, 9))
    lg.add_argument("--color", help="cor em hex (ex: 00ff00)")
    lg.add_argument("--wait", type=float, default=0.0)
    lg.set_defaults(func=cmd_set_light)

    w = sub.add_parser("watch", help="mostra os bytes que mudam nos reports (somente leitura)")
    w.add_argument("--seconds", type=int, default=30)
    w.add_argument("--interval", type=float, default=0.3)
    w.set_defaults(func=cmd_watch)

    pr = sub.add_parser("probe", help="lê os reports 0x0b, 0x06, 0x05 e 0x04 via handshake A0")
    pr.add_argument("--wait", type=float, default=0.0, help="segundos para aguardar o mouse acordar")
    pr.set_defaults(func=cmd_probe)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
