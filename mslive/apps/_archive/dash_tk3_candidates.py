import queue
import threading
import tkinter as tk

from mslive.apps.ms42_live import MS42Live

OIL_M = 0.796098
OIL_B = -48.0137

TEMP_BYTE_INDICES = [10, 11, 12, 13, 14]  # common “temp-ish” region in your frames


def temp_from_raw(raw: int) -> float:
    return raw * OIL_M + OIL_B


class Dash:
    def __init__(self, root: tk.Tk, port: str, hz: float = 6.0):
        self.root = root
        self.port = port
        self.hz = hz
        self.q: queue.Queue[object] = queue.Queue()
        self.running = True

        root.title("MS42 Live (DS2) — Candidates")
        root.geometry("720x420")

        self.lbl_rpm = tk.Label(root, text="RPM: --", font=("Segoe UI", 34))
        self.lbl_rpm.pack(pady=10)

        self.lbl_status = tk.Label(root, text="Status: starting…", font=("Segoe UI", 11))
        self.lbl_status.pack(pady=6)

        self.frame = tk.Frame(root)
        self.frame.pack(pady=10, fill="x")

        self.temp_labels = []
        for idx in TEMP_BYTE_INDICES:
            lbl = tk.Label(self.frame, text=f"resp[{idx}]: --  =>  --.- °C", font=("Consolas", 16), anchor="w")
            lbl.pack(fill="x", padx=20, pady=2)
            self.temp_labels.append(lbl)

        self.live = MS42Live(port=port, baud=9600, debug=False)

        self.t = threading.Thread(target=self.worker, daemon=True)
        self.t.start()

        self.root.after(50, self.ui_tick)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def worker(self):
        try:
            for sample in self.live.stream_general(hz=self.hz):
                # We need the raw response bytes too; simplest is to re-read in the worker.
                # MS42Live currently returns decoded only; so we call read_general() and then
                # ALSO ask MS42Live to expose last raw in the next iteration if you want.
                # For now, we’ll re-open a minimal path: use MS42Live.read_general() which decodes,
                # and also pull raw temp bytes by reading a frame here.
                # We’ll do it by calling the internal send again to avoid refactor.
                # (If you prefer, I’ll refactor MS42Live to return raw frame cleanly.)

                # Access the underlying DS2 and request a fresh general frame:
                resp = self.live._send_with_recovery(bytes.fromhex("12 05 0B 03"))

                rpm = (resp[3] << 8) | resp[4]
                temps = []
                for i in TEMP_BYTE_INDICES:
                    raw = resp[i]
                    temps.append((i, raw, temp_from_raw(raw)))

                self.q.put((rpm, temps))
        except Exception as e:
            self.q.put(e)

    def ui_tick(self):
        try:
            while True:
                msg = self.q.get_nowait()

                if isinstance(msg, Exception):
                    self.lbl_status.config(text=f"Status: error ({msg})")
                    continue

                rpm, temps = msg
                self.lbl_rpm.config(text=f"RPM: {rpm:.0f}")
                self.lbl_status.config(text="Status: live")

                for lbl, (i, raw, tc) in zip(self.temp_labels, temps):
                    lbl.config(text=f"resp[{i:2d}]: {raw:3d}  =>  {tc:5.1f} °C")

        except queue.Empty:
            pass

        if self.running:
            self.root.after(50, self.ui_tick)

    def on_close(self):
        self.running = False
        try:
            self.live.close()
        finally:
            self.root.destroy()


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--port", required=True)
    p.add_argument("--hz", type=float, default=6.0)
    args = p.parse_args()

    root = tk.Tk()
    Dash(root, port=args.port, hz=args.hz)
    root.mainloop()


if __name__ == "__main__":
    main()
