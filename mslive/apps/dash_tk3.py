# mslive/apps/dash_tk3.py
from __future__ import annotations
import argparse
import csv
import time
import tkinter as tk
from tkinter import ttk

from mslive.core.ds2 import DS2, DS2Config
from mslive.decoders.ms42_general import decode_general

REQ_GENERAL = bytes.fromhex("12 05 0B 03")

class EMA:
    def __init__(self, alpha: float):
        self.alpha = alpha
        self.v = None

    def update(self, x: float) -> float:
        if self.v is None:
            self.v = x
        else:
            self.v = self.alpha * x + (1.0 - self.alpha) * self.v
        return self.v

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="COM1 / COM3 / etc")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--hz", type=float, default=5.0)
    ap.add_argument("--log", default=None, help="optional csv path")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    d = DS2(DS2Config(port=args.port, baud=args.baud, debug=args.debug))
    d.open()
    d.initialized = True  # IMPORTANT: match your proven working path

    log_f = None
    log_w = None
    if args.log:
        log_f = open(args.log, "w", newline="")
        log_w = csv.writer(log_f)
        log_w.writerow(["ts", "rpm", "coolant_c", "oil_c", "iat_c"] + [f"b{i}" for i in range(32)])

    root = tk.Tk()
    root.title("MS42 Live")

    frm = ttk.Frame(root, padding=12)
    frm.grid(row=0, column=0, sticky="nsew")

    vars_ = {
        "rpm": tk.StringVar(value="—"),
        "cool": tk.StringVar(value="—"),
        "oil": tk.StringVar(value="—"),
        "iat": tk.StringVar(value="—"),
        "status": tk.StringVar(value="Connected"),
    }

    def row(r, label, var):
        ttk.Label(frm, text=label, font=("Segoe UI", 12, "bold")).grid(row=r, column=0, sticky="w", pady=4)
        ttk.Label(frm, textvariable=var, font=("Consolas", 18)).grid(row=r, column=1, sticky="e", pady=4)

    row(0, "RPM", vars_["rpm"])
    row(1, "Coolant °C", vars_["cool"])
    row(2, "Oil °C", vars_["oil"])
    row(3, "IAT °C", vars_["iat"])

    ttk.Label(frm, textvariable=vars_["status"]).grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))

    ema_rpm = EMA(alpha=0.35)
    ema_cool = EMA(alpha=0.25)
    ema_oil = EMA(alpha=0.20)
    ema_iat = EMA(alpha=0.30)

    period_ms = int(1000 / max(args.hz, 0.2))

    def tick():
        try:
            resp = d.send(REQ_GENERAL)
            g = decode_general(resp)

            # smoothing makes the UI nicer, especially IAT
            rpm = int(round(ema_rpm.update(float(g.rpm))))
            cool = ema_cool.update(g.coolant_c)
            oil = ema_oil.update(g.oil_c)
            iat = ema_iat.update(g.iat_c)

            vars_["rpm"].set(f"{rpm:d}")
            vars_["cool"].set(f"{cool:0.1f}")
            vars_["oil"].set(f"{oil:0.1f}")
            vars_["iat"].set(f"{iat:0.1f}")
            vars_["status"].set("OK")

            if log_w:
                log_w.writerow([time.time(), g.rpm, g.coolant_c, g.oil_c, g.iat_c] + list(resp[:32]))
                log_f.flush()

        except Exception as e:
            vars_["status"].set(f"ERR: {e}")

        root.after(period_ms, tick)

    def on_close():
        try:
            if log_f:
                log_f.close()
        finally:
            d.close()
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.after(100, tick)
    root.mainloop()

if __name__ == "__main__":
    main()
