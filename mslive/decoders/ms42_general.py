# mslive/decoders/ms42_general.py
from __future__ import annotations
from dataclasses import dataclass

def u16be(buf: bytes, i: int) -> int:
    return (buf[i] << 8) | buf[i + 1]

def temp_075(raw: int) -> float:
    return raw * 0.75 - 48.0

def temp_oil(raw: int) -> float:
    return raw * 0.79607843 - 48.0

@dataclass(frozen=True)
class Ms42General:
    rpm: int
    coolant_c: float
    oil_c: float
    iat_c: float

def decode_general(resp: bytes) -> Ms42General:
    """
    resp is the full DS2 response bytes (b0..).
    Mapping derived from your CSV behaviour:
      rpm       = u16be(15)
      coolant   = b11 (0.75x - 48)
      oil       = b12 (0.79607843x - 48)
      iat       = b22 (0.75x - 48)
    """
    rpm = u16be(resp, 15)
    coolant = temp_075(resp[11])
    oil = temp_oil(resp[12])
    iat = temp_075(resp[22])

    return Ms42General(rpm=rpm, coolant_c=coolant, oil_c=oil, iat_c=iat)
