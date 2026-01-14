from __future__ import annotations

import argparse
import sys
from typing import Optional

import serial

from mslive.core.ds2 import DS2, DS2Config
from mslive.core.transport import list_serial_ports
from mslive.util.paths import default_log_name, resolve_log_path


def add_profile_arg(ap: argparse.ArgumentParser, default: str = "ms42") -> None:
    ap.add_argument("--profile", default=default, help="ECU profile (default: ms42)")


def add_common_args(
    ap: argparse.ArgumentParser,
    *,
    default_baud: int = 9600,
    default_hz: float = 10.0,
) -> None:
    ap.add_argument("--baud", type=int, default=default_baud)
    ap.add_argument("--hz", type=float, default=default_hz)
    ap.add_argument("--debug", action="store_true")
    add_profile_arg(ap)


def add_port_or_replay(
    ap: argparse.ArgumentParser,
    *,
    port_help: str = "COMx on Windows or /dev/ttyUSB0 on Linux",
    replay_help: str = "Path to CSV log with b0..b31 to simulate MS42",
) -> None:
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--port", help=port_help)
    group.add_argument("--replay", help=replay_help)


def resolve_log_path_from_args(args: argparse.Namespace, arg_name: str, mode: str) -> str:
    profile = getattr(args, "profile", "ms42")
    default_name = default_log_name(profile, mode)
    path = resolve_log_path(getattr(args, arg_name), default_name)
    return str(path)


def _print_port_help() -> None:
    print("Port examples: Windows COM3, Linux /dev/ttyUSB0.", file=sys.stderr)
    ports = list_serial_ports(include_all=True)
    if not ports:
        print("Available ports: (none found)", file=sys.stderr)
        return
    print("Available ports:", file=sys.stderr)
    for p in ports:
        desc = p.get("description") or "unknown"
        hwid = p.get("hwid") or ""
        print(f"- {p['device']}: {desc} {hwid}".rstrip(), file=sys.stderr)


def open_ds2_or_exit(
    *,
    port: str,
    baud: int,
    debug: bool,
    timeout: float = 1.5,
    inter_byte_timeout: float = 0.05,
) -> DS2:
    d = DS2(DS2Config(port=port, baud=baud, debug=debug, timeout=timeout, inter_byte_timeout=inter_byte_timeout))
    try:
        d.open()
    except serial.SerialException as exc:
        print(f"Failed to open serial port '{port}': {exc}", file=sys.stderr)
        _print_port_help()
        raise SystemExit(1)
    return d
