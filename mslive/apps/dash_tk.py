import time
import threading
import queue
import tkinter as tk

from mslive.apps.poller import poll_general
from mslive.apps.decode import Channel, decode

CHANNELS = [
    Channel("rpm", "u16be", 3, 1.0, 0.0),
    Channel("temp_x_c", "u8", 10, 0.8, -48.0),
]

class App:
    def __init__(self, root: tk.Tk, port: str):
        self.root = root
        self.port = port
        self.q: queue.Queue[dict] = queue.Queue()
        self.running = True

        root.title("MS42 Live Dash (DS2)")
        root.geometry("420x220")

        self.lbl_rpm = tk.Label(root, text="RPM: --", font=("Segoe UI", 28))
        self.lbl_rpm.pack(pady=10)

        self.lbl_temp = tk.Label(root, text="TempX: --.- °C", font=("Segoe UI", 20))
        self.lbl_temp.pack(pady=5)

        self.lbl_status = tk.Label(root, text="Status: starting...", font=("Segoe UI", 10))
        self.lbl_status.pack(pady=10)

        t = threading.Thread(target=self.worker, daemon=True)
        t.start()

        self.root.after(50, self.ui_tick)

        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def worker(self):
        try:
            for resp in poll_general(self.port, seconds=10**9, hz=6.0):
                vals = decode(resp, CHANNELS)

                # RPM display: if it’s “close but not exact”, we’ll correct scaling after you confirm.
                rpm = vals["rpm"]
                temp = vals["temp_x_c"]

                self.q.put({
                    "rpm": rpm,
                    "temp": temp,
                    "ts": time.time(),
                })
        except Exception as e:
            self.q.put({"error": str(e)})

    def ui_tick(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if "error" in msg:
                    self.lbl_status.config(text=f"Error: {msg['error']}")
                    break

                self.lbl_rpm.config(text=f"RPM: {msg['rpm']:.0f}")
                self.lbl_temp.config(text=f"TempX: {msg['temp']:.1f} °C")
                self.lbl_status.config(text="Status: live")
        except queue.Empty:
            pass

        if self.running:
            self.root.after(50, self.ui_tick)

    def on_close(self):
        self.running = False
        self.root.destroy()

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--port", required=True, help="COM1 on Windows, /dev/ttyUSB0 on Linux")
    args = p.parse_args()

    root = tk.Tk()
    App(root, args.port)
    root.mainloop()

if __name__ == "__main__":
    main()
