# mslive/core/replay.py
from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

REQ_GENERAL = bytes.fromhex("12 05 0B 03")

@dataclass
class ReplayConfig:
    csv_path: str
    realtime: bool = True     # True: respect ts deltas; False: run as fast as possible
    loop: bool = True         # loop when end is reached
    speed: float = 1.0        # 2.0 = 2x faster than recorded time
    ts_column: str = "ts"
    b_prefix: str = "b"       # columns b0..b31

class ReplayDS2:
    """
    Minimal drop-in stand-in for DS2 used by dash/logger:
      - open()
      - close()
      - send(payload) -> bytes

    It replays recorded DS2 responses from CSV columns b0..b31.
    Currently supports REQ_GENERAL only; extend with mapping if you add more jobs later.
    """
    def __init__(self, cfg: ReplayConfig):
        self.cfg = cfg
        self.frames: List[bytes] = []
        self.ts: List[float] = []
        self.i = 0
        self._t0_real: Optional[float] = None
        self._t0_log: Optional[float] = None

    def open(self) -> None:
        p = Path(self.cfg.csv_path)
        if not p.exists():
            raise FileNotFoundError(self.cfg.csv_path)

        with p.open("r", newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            needed = [f"{self.cfg.b_prefix}{i}" for i in range(32)]
            for row in r:
                try:
                    t = float(row[self.cfg.ts_column])
                except Exception:
                    # If ts is missing/invalid, fall back to monotonic-ish indexing
                    t = float(len(self.ts))

                b = []
                ok = True
                for col in needed:
                    if col not in row:
                        ok = False
                        break
                    try:
                        b.append(int(row[col]))
                    except Exception:
                        ok = False
                        break

                if not ok:
                    continue

                self.ts.append(t)
                self.frames.append(bytes((x & 0xFF) for x in b))

        if not self.frames:
            raise ValueError("No valid frames found in CSV (need b0..b31 columns).")

        self.i = 0
        self._t0_real = time.time()
        self._t0_log = self.ts[0]

    def close(self) -> None:
        self.frames = []
        self.ts = []
        self.i = 0
        self._t0_real = None
        self._t0_log = None

    def _sleep_to_match_time(self, idx: int) -> None:
        if not self.cfg.realtime:
            return
        assert self._t0_real is not None and self._t0_log is not None

        # target log elapsed, scaled
        log_elapsed = (self.ts[idx] - self._t0_log) / max(self.cfg.speed, 1e-6)
        target_real = self._t0_real + log_elapsed
        now = time.time()
        dt = target_real - now
        if dt > 0:
            time.sleep(dt)

    def send(self, payload_no_chk: bytes) -> bytes:
        # Only support GENERAL for now (expand later)
        if payload_no_chk != REQ_GENERAL:
            raise NotImplementedError(
                f"ReplayDS2 only supports REQ_GENERAL for now. Got: {payload_no_chk.hex(' ')}"
            )

        if not self.frames:
            raise RuntimeError("ReplayDS2 not opened")

        # Timing
        self._sleep_to_match_time(self.i)

        resp = self.frames[self.i]

        # advance
        self.i += 1
        if self.i >= len(self.frames):
            if self.cfg.loop:
                self.i = 0
                self._t0_real = time.time()
                self._t0_log = self.ts[0]
            else:
                self.i = len(self.frames) - 1  # hold last frame

        return resp
