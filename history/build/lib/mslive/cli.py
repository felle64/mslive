from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional

from .core.record import Recorder, Replayer
from .core.scheduler import PollItem, PollScheduler
from .core.transport import SerialConfig, SerialTransport, list_serial_ports
from .core.util import bytes_to_hex, hex_to_bytes


def cmd_ports(_: argparse.Namespace) -> int:
    ports = list_serial_ports()
    if not ports:
        print("No serial ports found.")
        return 1
    for p in ports:
        print(f"- {p['device']}: {p['description']}  ({p.get('hwid')})")
    return 0


def cmd_ports(args: argparse.Namespace) -> int:
    ports = list_serial_ports(include_all=args.all)
    if not ports:
        print("No serial ports found.")
        return 1
    for p in ports:
        print(f"- {p['device']}: {p['description']}  ({p.get('hwid')})")
    return 0



def _read_loop(t: SerialTransport, rec: Optional[Recorder] = None, duration_s: float = 5.0) -> None:
    end = time.monotonic() + duration_s
    while time.monotonic() < end:
        b = t.read(4096)
        if b:
            if rec:
                rec.write("rx", b)
            print(f"RX {len(b):4d}: {bytes_to_hex(b)}")
        time.sleep(0.001)


def cmd_send(args: argparse.Namespace) -> int:
    payload = hex_to_bytes(args.hex)
    rec = None
    rec_f = None
    if args.record:
        rec_f = open(args.record, "wb")
        rec = Recorder(rec_f)

    t = SerialTransport(SerialConfig(port=args.port, baud=args.baud, timeout_s=0.05))
    t.open()
    t.flush()

    if rec:
        rec.write("tx", payload)
    t.write(payload)
    print(f"TX {len(payload):4d}: {bytes_to_hex(payload)}")

    _read_loop(t, rec=rec, duration_s=args.read_for)

    t.close()
    if rec_f:
        rec_f.close()
    return 0


def cmd_poll(args: argparse.Namespace) -> int:
    poll_obj = json.loads(Path(args.poll_file).read_text(encoding="utf-8"))
    polls: list[PollItem] = []
    for it in poll_obj.get("polls", []):
        polls.append(
            PollItem(
                name=str(it["name"]),
                payload=hex_to_bytes(str(it["hex"])),
                interval_s=float(it["interval_ms"]) / 1000.0,
            )
        )
    if not polls:
        raise SystemExit("poll-file has no polls[] entries")

    rec = None
    rec_f = None
    if args.record:
        rec_f = open(args.record, "wb")
        rec = Recorder(rec_f)

    t = SerialTransport(SerialConfig(port=args.port, baud=args.baud, timeout_s=0.01))
    t.open()
    t.flush()

    def send_func(payload: bytes) -> None:
        if rec:
            rec.write("tx", payload)
        t.write(payload)

    sched = PollScheduler(items=polls, send_func=send_func)

    print(f"Polling {len(polls)} items on {args.port} @ {args.baud}. Ctrl+C to stop.")
    start = time.monotonic()
    try:
        while True:
            # one scheduler step (tight loop)
            now = time.monotonic()
            for it in sched.items:
                if now >= it.next_due:
                    send_func(it.payload)
                    it.next_due = now + it.interval_s

            # read any inbound
            b = t.read(4096)
            if b:
                if rec:
                    rec.write("rx", b)
                if args.print_rx:
                    print(f"RX {len(b):4d}: {bytes_to_hex(b)}")

            if args.stop_after and (time.monotonic() - start) >= args.stop_after:
                break
            time.sleep(0.001)
    except KeyboardInterrupt:
        pass
    finally:
        t.close()
        if rec_f:
            rec_f.close()
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    with open(args.file, "rb") as f:
        rp = Replayer(f)
        last_ts = None
        for fr in rp:
            if args.realtime:
                if last_ts is not None:
                    dt = fr.ts - last_ts
                    if dt > 0:
                        time.sleep(min(dt, 0.25))
                last_ts = fr.ts
            print(f"{fr.direction.upper()} {fr.ts:.3f} {len(fr.payload):4d}: {bytes_to_hex(fr.payload)}")
    return 0
    
def cmd_open(args: argparse.Namespace) -> int:
    t = SerialTransport(SerialConfig(port=args.port, baud=args.baud, timeout_s=0.2))
    t.open()
    print(f"Opened {args.port} @ {args.baud}.")
    t.close()
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(prog="mslive")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("ports", help="List serial ports")
    sp.add_argument("--all", action="store_true", help="Show all ports, including ttyS*")
    sp.set_defaults(func=cmd_ports)


    sp = sub.add_parser("open", help="Open a serial port (sanity check)")
    sp.add_argument("--port", required=True)
    sp.add_argument("--baud", type=int, default=10400)
    sp.set_defaults(func=cmd_open)

    sp = sub.add_parser("send", help="Send one hex payload and print responses")
    sp.add_argument("--port", required=True)
    sp.add_argument("--baud", type=int, default=10400)
    sp.add_argument("--hex", required=True, help='e.g. "80 10 F1 3E 00"')
    sp.add_argument("--read-for", type=float, default=2.0)
    sp.add_argument("--record", help="Write raw TX/RX recording file (.mslr)")
    sp.set_defaults(func=cmd_send)

    sp = sub.add_parser("poll", help="Poll request(s) from a JSON file")
    sp.add_argument("--port", required=True)
    sp.add_argument("--baud", type=int, default=10400)
    sp.add_argument("--poll-file", required=True)
    sp.add_argument("--record", help="Write raw TX/RX recording file (.mslr)")
    sp.add_argument("--print-rx", action="store_true", help="Print RX frames as hex")
    sp.add_argument("--stop-after", type=float, default=None, help="Stop after N seconds")
    sp.set_defaults(func=cmd_poll)

    sp = sub.add_parser("replay", help="Replay a .mslr recording")
    sp.add_argument("--file", required=True)
    sp.add_argument("--realtime", action="store_true", help="Sleep to approximate original timing")
    sp.set_defaults(func=cmd_replay)

    args = ap.parse_args()
    rc = args.func(args)
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
