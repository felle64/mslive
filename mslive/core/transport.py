from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional, Protocol

import serial
from serial.tools import list_ports


class Transport(Protocol):
    def open(self) -> None: ...
    def close(self) -> None: ...
    def write(self, data: bytes) -> int: ...
    def read(self, max_bytes: int = 4096) -> bytes: ...
    def flush(self) -> None: ...


@dataclass
class SerialConfig:
    port: str
    baud: int = 10400
    timeout_s: float = 0.1  # read timeout
    write_timeout_s: float = 0.2
    inter_byte_timeout_s: Optional[float] = None


class SerialTransport:
    def __init__(self, cfg: SerialConfig):
        self.cfg = cfg
        self.ser: Optional[serial.Serial] = None

    def open(self) -> None:
        if self.ser and self.ser.is_open:
            return
        self.ser = serial.Serial(
            port=self.cfg.port,
            baudrate=self.cfg.baud,
            timeout=self.cfg.timeout_s,
            write_timeout=self.cfg.write_timeout_s,
            inter_byte_timeout=self.cfg.inter_byte_timeout_s,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )
        # Small settling delay is often helpful for USB serial
        time.sleep(0.05)

    def close(self) -> None:
        if self.ser:
            try:
                self.ser.close()
            finally:
                self.ser = None

    def flush(self) -> None:
        if not self.ser:
            return
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

    def write(self, data: bytes) -> int:
        if not self.ser:
            raise RuntimeError("Serial not open")
        return self.ser.write(data)

    def read(self, max_bytes: int = 4096) -> bytes:
        if not self.ser:
            raise RuntimeError("Serial not open")
        # Read whatever is available up to max_bytes
        waiting = self.ser.in_waiting
        n = min(max_bytes, waiting if waiting > 0 else max_bytes)
        return self.ser.read(n)


def list_serial_ports(include_all: bool = False) -> list[dict]:
    out = []
    for p in list_ports.comports():
        desc = (p.description or "").strip()
        dev = (p.device or "").strip()

        # Default: hide "n/a" ports (common on Linux ttyS*)
        if not include_all:
            if desc.lower() in {"n/a", "unknown"}:
                continue
            # Also hide plain ttyS* even if desc is empty
            if dev.startswith("/dev/ttyS"):
                continue

        out.append(
            {
                "device": dev,
                "description": desc,
                "hwid": p.hwid,
                "manufacturer": getattr(p, "manufacturer", None),
                "serial_number": getattr(p, "serial_number", None),
                "vid": getattr(p, "vid", None),
                "pid": getattr(p, "pid", None),
            }
        )

    # Prefer USB serial devices first
    def _rank(x: dict) -> tuple[int, str]:
        d = x["device"] or ""
        return (0 if ("ttyUSB" in d or "ttyACM" in d or d.upper().startswith("COM")) else 1, d)

    out.sort(key=_rank)
    return out

