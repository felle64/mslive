# mslive/apps/logger_csv.py
import argparse
import csv
import time
from dataclasses import dataclass

from mslive.core.ds2 import DS2, DS2Config

REQ_GENERAL = bytes.fromhex("12 05 0B 03")  # checksum appended internally by your DS2.send()

def u16be(resp: bytes, i: int) -> int:
    return (resp[i] << 8) | resp[i + 1]

def temp_coolant(raw: int) -> float:
    # MS4x coolant / IAT style
    return raw * 0.75 - 48.0

def temp_oil(raw: int) -> float:
    # MS4x oil style
    return raw * 0.79607843 - 48.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="COM port (e.g. COM1, COM3)")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--hz", type=float, default=5.0, help="sample rate")
    ap.add_argument("--out", default=None, help="output csv path")
    ap.add_argument("--seconds", type=float, default=0, help="0 = run until Ctrl+C")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    out = args.out or time.strftime("ms42_%Y%m%d_%H%M%S.csv")

    d = DS2(DS2Config(port=args.port, baud=args.baud, debug=args.debug))
    d.open()

    # IMPORTANT: match what made your CLI reliable
    # (skip init; your ECU responds fine to direct requests)
    d.initialized = True

    period = 1.0 / max(args.hz, 0.1)
    t0 = time.time()

    with open(out, "w", newline="") as f:
        w = csv.writer(f)

        # Log raw bytes too so we can map channels later
        # b0..bN will be the response bytes (0-based)
        header = ["ts", "rpm",
                  "t_raw_a", "t_oil_a_c", "t_cool_a_c",
                  "t_raw_b", "t_oil_b_c", "t_cool_b_c"] + [f"b{i}" for i in range(0, 32)]
        w.writerow(header)

        try:
            while True:
                now = time.time()
                if args.seconds and (now - t0) >= args.seconds:
                    break

                resp = d.send(REQ_GENERAL)

                # RPM: keep what you validated as correct in your tests
                rpm = u16be(resp, 15)

                # Two candidate temperature bytes (adjust indices once we confirm)
                # Keep BOTH interpretations in the log.
                raw_a = resp[10]
                raw_b = resp[12]

                row = [
                    now,
                    rpm,
                    raw_a, round(temp_oil(raw_a), 1), round(temp_coolant(raw_a), 1),
                    raw_b, round(temp_oil(raw_b), 1), round(temp_coolant(raw_b), 1),
                ] + list(resp[:32])

                w.writerow(row)
                f.flush()

                time.sleep(period)

        except KeyboardInterrupt:
            pass
        finally:
            d.close()

    print(f"Wrote {out}")

if __name__ == "__main__":
    main()
