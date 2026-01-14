# mslive/apps/logger_csv.py
import argparse
import csv
import time

from mslive.core.ds2 import DS2, DS2Config

REQ_GENERAL = bytes.fromhex("12 05 0B 03")  # checksum appended internally by DS2.send()


def u16be(resp: bytes, i: int) -> int:
    return (resp[i] << 8) | resp[i + 1]


def temp_coolant(raw: int) -> float:
    return raw * 0.75 - 48.0


def temp_oil(raw: int) -> float:
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
    d.initialized = True  # proven-good path

    period = 1.0 / max(args.hz, 0.1)
    t0 = time.time()
    next_t = t0  # NEW: stable timing

    with open(out, "w", newline="") as f:
        w = csv.writer(f)

        header = [
            "ts",
            "rpm",
            "maf_kgph",       # CHANGED (was speed_kmh)
            "vbatt_v",
            "load_raw",
            "load_pct_approx",  # NEW
            "throttle_raw",     # CHANGED (thr_raw6)
            "throttle2_raw",    # CHANGED (thr_raw7)
            "t_raw_a",
            "t_oil_a_c",
            "t_cool_a_c",
            "t_raw_b",
            "t_oil_b_c",
            "t_cool_b_c",
        ] + [f"b{i}" for i in range(0, 32)]
        w.writerow(header)

        try:
            while True:
                now = time.time()
                if args.seconds and (now - t0) >= args.seconds:
                    break

                resp = d.send(REQ_GENERAL)

                rpm = u16be(resp, 15)

                # CHANGED: this behaves like airflow, not road speed
                maf_kgph = u16be(resp, 8) / 10.0

                vbatt_v = resp[23] / 10.0

                load_raw = resp[19]
                load_pct = load_raw / 2.55  # approx; rename later if needed

                throttle_raw = resp[6]   # your thr_raw6
                throttle2_raw = resp[7]  # your thr_raw7

                raw_a = resp[10]
                raw_b = resp[12]

                row = [
                    now,
                    rpm,
                    round(maf_kgph, 1),
                    round(vbatt_v, 1),
                    load_raw,
                    round(load_pct, 1),
                    throttle_raw,
                    throttle2_raw,
                    raw_a,
                    round(temp_oil(raw_a), 1),
                    round(temp_coolant(raw_a), 1),
                    raw_b,
                    round(temp_oil(raw_b), 1),
                    round(temp_coolant(raw_b), 1),
                ] + list(resp[:32])

                w.writerow(row)
                f.flush()

                # NEW: stable scheduler (don’t drift)
                next_t += period
                sleep_s = next_t - time.time()
                if sleep_s > 0:
                    time.sleep(sleep_s)

        except KeyboardInterrupt:
            pass
        finally:
            d.close()

    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
