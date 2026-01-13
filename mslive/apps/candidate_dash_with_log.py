# mslive/apps/candidate_dash_with_log.py
import csv
import time
from pathlib import Path
import queue
import threading
import tkinter as tk

from mslive.apps.ms42_live import MS42Live

REQ_GENERAL = bytes.fromhex("12 05 0B 03")
CANDIDATE_BYTES = list(range(10, 21))  # 10..20


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def parse_rpm(resp: bytes) -> int:
    return (resp[3] << 8) | resp[4]


class Dash:
    def __init__(self, root: tk.Tk, port: str, hz: float, out_path: Path):
        self.root = root
        self.port = port
        self.hz = hz
        self.out_path = out_path
        self.q: queue.Queue[object] = queue.Queue()
        self.running = True

        root.title("MS42 DS2 Candidates (with logging)")
        root.geometry("820x520")

        self.lbl_rpm = tk.Label(root, text="RPM: --", font=("Segoe UI", 34))
        self.lbl_rpm.pack(pady=10)

        self.lbl_status = tk.Label(root, text="Status: starting…", font=("Segoe UI", 11))
        self.lbl_status.pack(pady=6)

        self.frame = tk.Frame(root)
        self.frame.pack(pady=10, fill="x")

        self.lines = []
        for idx in CANDIDATE_BYTES:
            lbl = tk.Label(self.frame, text=f"b{idx}: --", font=("Consolas", 16), anchor="w")
            lbl.pack(fill="x", padx=20, pady=1)
            self.lines.append(lbl)

        self.live = MS42Live(port=port, baud=9600, debug=False)

        ensure_parent(out_path)
        self.csv_file = out_path.open("w", newline="", encoding="utf-8")
        self.csv = csv.writer(self.csv_file)

        header = ["ts", "rpm", "status", "len"] + [f"b{idx}" for idx in CANDIDATE_BYTES] + ["raw_hex"]
        self.csv.writerow(header)
        self.csv_file.flush()

        self.t = threading.Thread(target=self.worker, daemon=True)
        self.t.start()

        self.root.after(50, self.ui_tick)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def worker(self):
        period = 1.0 / self.hz
        try:
            while self.running:
                t0 = time.time()
                resp = self.live._send_with_recovery(REQ_GENERAL)

                rpm = parse_rpm(resp)
                status = resp[2]
                ln = resp[1]

                # Log row
                row = [f"{t0:.3f}", rpm, f"0x{status:02X}", ln]
                for idx in CANDIDATE_BYTES:
                    row.append(resp[idx] if idx < len(resp) else "")
                row.append(resp.hex(" "))
                self.csv.writerow(row)
                self.csv_file.flush()

                # UI payload
                values = {idx: resp[idx] for idx in CANDIDATE_BYTES if idx < len(resp)}
                self.q.put((rpm, status, ln, values))

                dt = time.time() - t0
                if dt < period:
                    time.sleep(period - dt)

        except Exception as e:
            self.q.put(e)

    def ui_tick(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if isinstance(msg, Exception):
                    self.lbl_status.config(text=f"Status: error ({msg})")
                    continue

                rpm, status, ln, values = msg
                self.lbl_rpm.config(text=f"RPM: {rpm:.0f}")
                self.lbl_status.config(text=f"Status: live (0x{status:02X}, len={ln})")

                for lbl, idx in zip(self.lines, CANDIDATE_BYTES):
                    v = values.get(idx, None)
                    lbl.config(text=f"b{idx:02d}: {v if v is not None else '--'}")

        except queue.Empty:
            pass

        if self.running:
            self.root.after(50, self.ui_tick)

    def on_close(self):
        self.running = False
        try:
            self.live.close()
        finally:
            try:
                self.csv_file.close()
            except Exception:
                pass
            self.root.destroy()


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--port", required=True)
    p.add_argument("--hz", type=float, default=6.0)
    p.add_argument("--out", default="", help="CSV output path")
    args = p.parse_args()

    if args.out:
        out_path = Path(args.out)
    else:
        out_path = Path("logs") / time.strftime("ms42_candidates_%Y%m%d_%H%M%S.csv")

    root = tk.Tk()
    Dash(root, port=args.port, hz=args.hz, out_path=out_path)
    root.mainloop()


if __name__ == "__main__":
    main()
