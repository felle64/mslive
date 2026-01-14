# mslive/core/signals_ms42.py
from __future__ import annotations

from dataclasses import dataclass

def u16be(hi: int, lo: int) -> int:
    return ((hi & 0xFF) << 8) | (lo & 0xFF)

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

@dataclass(frozen=True)
class MS42Offsets:
    coolant_c: float = 0.0
    oil_c: float = 0.0
    iat_c: float = 0.0

def decode_ms42_gen(resp: bytes, offsets: MS42Offsets = MS42Offsets()) -> dict:
    """
    Expects full DS2 GEN response, e.g.:
      12 26 a0 ... (38 bytes total) ... chk
    Indices below are based on your working logs.
    """
    if len(resp) < 26:
        raise ValueError(f"GEN response too short: {len(resp)} bytes")

    # Your confirmed RPM location
    rpm = u16be(resp[15], resp[16])

    # Speed looks like u16 at [8:10] scaled by 0.1 km/h
    speed_kmh = u16be(resp[8], resp[9]) / 10.0

    # Battery voltage looks like resp[23]/10
    vbatt_v = resp[23] / 10.0

    # Keep your existing temps as-is in your codebase if already correct.
    # If you want them here, wire them to *your known-good formulas*.
    # Placeholders (set to None unless your app already computes them elsewhere):
    coolant_c = None
    oil_c = None
    iat_c = None

    # Candidate raw channels (rename after INPA confirmation)
    load_raw = resp[19]  # strong transient behavior in driving logs
    thr_raw6 = resp[6]
    thr_raw7 = resp[7]

    out = {
        "rpm": rpm,
        "speed_kmh": speed_kmh,
        "vbatt_v": vbatt_v,
        "load_raw": load_raw,
        "thr_raw6": thr_raw6,
        "thr_raw7": thr_raw7,
        "coolant_c": coolant_c,
        "oil_c": oil_c,
        "iat_c": iat_c,
    }

    # Apply offsets only if values exist
    if out["coolant_c"] is not None:
        out["coolant_c"] = out["coolant_c"] + offsets.coolant_c
    if out["oil_c"] is not None:
        out["oil_c"] = out["oil_c"] + offsets.oil_c
    if out["iat_c"] is not None:
        out["iat_c"] = out["iat_c"] + offsets.iat_c

    return out
