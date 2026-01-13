from dataclasses import dataclass

@dataclass
class Channel:
    name: str
    kind: str          # "u8" or "u16be"
    index: int         # start index in resp
    scale: float = 1.0
    offset: float = 0.0

def u8(resp: bytes, i: int) -> int:
    return resp[i]

def u16be(resp: bytes, i: int) -> int:
    return (resp[i] << 8) | resp[i + 1]

def decode(resp: bytes, channels: list[Channel]) -> dict[str, float]:
    out = {}
    for ch in channels:
        if ch.kind == "u8":
            raw = u8(resp, ch.index)
        elif ch.kind == "u16be":
            raw = u16be(resp, ch.index)
        else:
            raise ValueError(f"Unknown kind: {ch.kind}")
        out[ch.name] = raw * ch.scale + ch.offset
    return out
