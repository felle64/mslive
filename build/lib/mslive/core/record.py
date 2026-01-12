from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from typing import BinaryIO, Iterator, Literal, Optional

Direction = Literal["tx", "rx"]

# Record format:
# magic "MSLR" (file header)
# then repeated:
#   double ts (seconds since epoch)
#   uint8 dir (0=tx, 1=rx)
#   uint32 len
#   bytes payload
_FILE_MAGIC = b"MSLR"
_REC_HDR = struct.Struct("<dBI")


@dataclass
class Frame:
    ts: float
    direction: Direction
    payload: bytes


class Recorder:
    def __init__(self, f: BinaryIO):
        self.f = f
        self._wrote_header = False

    def _ensure_header(self) -> None:
        if not self._wrote_header:
            self.f.write(_FILE_MAGIC)
            self._wrote_header = True

    def write(self, direction: Direction, payload: bytes, ts: Optional[float] = None) -> None:
        self._ensure_header()
        ts = time.time() if ts is None else ts
        dir_b = 0 if direction == "tx" else 1
        self.f.write(_REC_HDR.pack(ts, dir_b, len(payload)))
        self.f.write(payload)
        self.f.flush()


class Replayer:
    def __init__(self, f: BinaryIO):
        self.f = f
        magic = self.f.read(4)
        if magic != _FILE_MAGIC:
            raise ValueError("Not a valid MSLR recording (bad magic)")

    def __iter__(self) -> Iterator[Frame]:
        while True:
            hdr = self.f.read(_REC_HDR.size)
            if not hdr:
                break
            ts, dir_b, ln = _REC_HDR.unpack(hdr)
            payload = self.f.read(ln)
            if len(payload) != ln:
                raise ValueError("Corrupt recording (truncated payload)")
            direction: Direction = "tx" if dir_b == 0 else "rx"
            yield Frame(ts=ts, direction=direction, payload=payload)
