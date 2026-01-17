# mslive/apps/dash_tk2.py
import queue
import threading
import tkinter as tk

from mslive.apps.ms42_live import MS42Live, LiveSample


class Dash:
    def __init__(self, root: tk.Tk, port: str, hz: float = 6.0):
        self.root = root
        self.port = port
        self.hz = hz

        self.q: queue.Queue[object] = queue.Queue()
        self.running = True

        root.title("MS42 Live (DS2)")
        root.geometry("520x260")

        self.lbl_rpm = tk.Label(root, text="RPM: --", font=("Segoe UI", 34))
        self.lbl_rpm.pack(pady=12)

        self.lbl_temp = tk.Label(root, text="TempX: --.- °C", font=("Segoe UI", 22))
        self.lbl_temp.pack(pady=6)

        self.lbl_status = tk.Label(root, text="Status: starting…", font=("Segoe UI", 11))
        self.lbl_status.pack(pady=10)

        self.live = MS42Live(port=port, baud=9600, debug=False)

        self.t = threading.Thread(target=self.worker, daemon=True)
        self.t.start()

        self.root.after(50, self.ui_tick)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def worker(self):
        try:
            for sample in self.live.stream_general(hz=self.hz):
                self.q.put(sample)
        except Exception as e:
            self.q.put(e)

    def ui_tick(self):
        try:
            while True:
                msg = self.q.get_nowait()

                if isinstance(msg, Exception):
                    self.lbl_status.config(text=f"Status: error ({msg})")
                    continue

                assert isinstance(msg, LiveSample)
                self.lbl_rpm.config(text=f"RPM: {msg.rpm:.0f}")
                self.lbl_temp.config(text=f"TempX: {msg.temp_x_c:.1f} °C  (raw {msg.raw_temp_x})")
                self.lbl_status.config(text="Status: live")

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
    p.add_argument("--port", required=True, help="e.g. COM1 on Windows or /dev/ttyUSB0 on Linux")
    p.add_argument("--hz", type=float, default=6.0, help="Polling rate (Hz)")
    args = p.parse_args()

    root = tk.Tk()
    Dash(root, port=args.port, hz=args.hz)
    root.mainloop()


if __name__ == "__main__":
    main()
