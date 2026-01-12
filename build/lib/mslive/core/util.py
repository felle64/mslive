from __future__ import annotations

import binascii
from typing import Iterable


def hex_to_bytes(s: str) -> bytes:
    """
    Accepts:
      - "80 10 F1 3E 00"
      - "8010F13E00"
      - with optional 0x prefixes
    """
    cleaned = (
        s.replace("0x", "")
        .replace("0X", "")
        .replace(" ", "")
        .replace("\n", "")
        .replace("\t", "")
        .replace("-", "")
        .strip()
    )
    if len(cleaned) % 2 != 0:
        raise ValueError(f"Hex string has odd length: {len(cleaned)}")
    return binascii.unhexlify(cleaned)


def bytes_to_hex(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)


def clamp(n: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, n))


def chunk_iter(data: bytes, sizes: Iterable[int]) -> list[bytes]:
    out: list[bytes] = []
    idx = 0
    for sz in sizes:
        out.append(data[idx : idx + sz])
        idx += sz
    if idx != len(data):
        raise ValueError("chunk_iter sizes do not sum to data length")
    return out
