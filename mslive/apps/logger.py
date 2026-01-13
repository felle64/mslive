# mslive/apps/logger.py
import csv
import time
from pathlib import Path

from mslive.apps.ms42_live import MS42Live

REQ_GENERAL = bytes.fromhex("12 05 0B 03")

# Candidate byte indices to log (adjust any time)
CANDIDATE_BYTES = list(range(10, 21))  # 10..20 inclusive


def parse_rpm(resp: bytes) -> int:
    return (resp[3] << 8) | resp[4]


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def main():
    import argparse

    p = argparse.ArgumentParser(description="MS42 DS2 logger (CSV + raw frame)")
    p.add_argument("--port", required=True, help="COMx on Windows, /dev/ttyUSB0 on Linux")
    p.add_argument("--hz", type=float, default=6.0, help="Polling rate")
    p.add_argument("--out", default="", help="Output CSV path (default: logs/ms42_YYYYmmdd_HHMMSS.csv)")
    p.add_argument("--seconds", type=float, default=0.0, help="Stop after N seconds (0 = run until Ctrl+C)")
    args = p.parse_args()

    hz = args.hz
    period = 1.0 / hz

    if args.out:
        out_path = Path(args.out)
    else:
        out_path = Path("logs") / time.strftime("ms42_%Y%m%d_%H%M%S.csv")

    ensure_parent(out_path)

    live = MS42Live(port=args.port, baud=9600, debug=False)

    header = (
        ["ts", "rpm", "status", "len"]
        + [f"b{idx}" for idx in CANDIDATE_BYTES]
        + ["raw_hex"]
    )

    print(f"Logging to: {out_path}")
    print("Press Ctrl+C to stop." if args.seconds == 0 else f"Will stop after {args.seconds:.0f}s")

    t_end = time.time() + args.seconds if args.seconds > 0 else None

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)

        try:
            # Use the same streaming loop style as the GUI
            for _ in live.stream_general(hz=hz):
                t0 = time.time()

                # Fetch one raw general frame using the proven recovery path
                resp = live._send_with_recovery(REQ_GENERAL)

                rpm = parse_rpm(resp)
                status = resp[2]
                ln = resp[1]

                row = [f"{t0:.3f}", rpm, f"0x{status:02X}", ln]

                for idx in CANDIDATE_BYTES:
                    row.append(resp[idx] if idx < len(resp) else "")

                row.append(resp.hex(" "))

                w.writerow(row)
                f.flush()

                if t_end is not None and time.time() >= t_end:
                    break

                dt = time.time() - t0
                if dt < period:
                    time.sleep(period - dt)

        except KeyboardInterrupt:
            pass
        finally:
            live.close()

    print("Done.")


if __name__ == "__main__":
    main()
