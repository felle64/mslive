from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

from .util import hex_to_bytes


@dataclass
class PollItem:
    name: str
    payload: bytes
    interval_s: float
    next_due: float = 0.0


class PollScheduler:
    def __init__(
        self,
        items: list[PollItem],
        send_func: Callable[[bytes], None],
        tick_sleep_s: float = 0.002,
    ):
        self.items = items
        self.send_func = send_func
        self.tick_sleep_s = tick_sleep_s
        now = time.monotonic()
        for it in self.items:
            it.next_due = now

    @staticmethod
    def from_json(obj: dict) -> "PollScheduler":
        items: list[PollItem] = []
        for it in obj.get("polls", []):
            name = str(it["name"])
            payload = hex_to_bytes(str(it["hex"]))
            interval_ms = float(it["interval_ms"])
            items.append(PollItem(name=name, payload=payload, interval_s=interval_ms / 1000.0))
        raise_if_empty(items)
        return PollScheduler(items=items, send_func=lambda _: None)

    def run(self, stop_after_s: Optional[float] = None) -> None:
        start = time.monotonic()
        while True:
            now = time.monotonic()
            if stop_after_s is not None and (now - start) >= stop_after_s:
                return
            sent_any = False
            for it in self.items:
                if now >= it.next_due:
                    self.send_func(it.payload)
                    it.next_due = now + it.interval_s
                    sent_any = True
            time.sleep(self.tick_sleep_s if not sent_any else 0)


def raise_if_empty(items: list[PollItem]) -> None:
    if not items:
        raise ValueError("Poll list is empty")
