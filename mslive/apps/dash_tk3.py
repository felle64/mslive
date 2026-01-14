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


def u16be(resp: bytes, i: int) -> int:
    return (resp[i] << 8) | resp[i + 1]


class EMA:
    def __init__(self, alpha: float):
        self.alpha = alpha
        self.v = None

    def update(self, x: float) -> float:
        if self.alpha >= 0.999:
            self.v = x
            return x
        if self.v is None:
            self.v = x
        else:
            self.v = self.alpha * x + (1.0 - self.alpha) * self.v
        return self.v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="COM1 / COM3 / etc")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--hz", type=float, default=10.0)

    # smoothing knobs (default: NO rpm smoothing)
    ap.add_argument("--rpm-alpha", type=float, default=1.0, help="1.0=no smoothing, 0.2=heavy smoothing")
    ap.add_argument("--temp-alpha", type=float, default=0.25, help="smoothing for temps (0..1)")

    ap.add_argument("--log", default=None, help="optional csv path")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    d = DS2(DS2Config(port=args.port, baud=args.baud, debug=args.debug))
    d.open()
    d.initialized = True  # match your proven working path

    # Optional log
    log_f = None
    log_w = None
    if args.log:
        log_f = open(args.log, "w", newline="", encoding="utf-8")
        log_w = csv.writer(log_f)
        log_w.writerow(
            ["ts", "rpm", "coolant_c", "oil_c", "iat_c", "maf_kgph", "vbatt_v", "load_pct", "thr_raw", "thr2_raw"]
            + [f"b{i}" for i in range(32)]
        )
        log_f.flush()

    root = tk.Tk()
    root.title("MS42 Live")
    root.geometry("520x360")

    frm = ttk.Frame(root, padding=12)
    frm.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    vars_ = {
        "rpm": tk.StringVar(value="—"),
        "cool": tk.StringVar(value="—"),
        "oil": tk.StringVar(value="—"),
        "iat": tk.StringVar(value="—"),
        "maf": tk.StringVar(value="—"),
        "vbatt": tk.StringVar(value="—"),
        "load": tk.StringVar(value="—"),
        "thr": tk.StringVar(value="—"),
        "thr2": tk.StringVar(value="—"),
        "status": tk.StringVar(value="Connected"),
        "timeouts": tk.StringVar(value="Timeouts: 0"),
        "lasterr": tk.StringVar(value=""),
    }

    def add_row(r: int, label: str, var: tk.StringVar):
        ttk.Label(frm, text=label, font=("Segoe UI", 11, "bold")).grid(row=r, column=0, sticky="w", pady=3)
        ttk.Label(frm, textvariable=var, font=("Consolas", 16)).grid(row=r, column=1, sticky="e", pady=3)

    r = 0
    add_row(r, "RPM", vars_["rpm"]); r += 1
    add_row(r, "Coolant °C", vars_["cool"]); r += 1
    add_row(r, "Oil °C", vars_["oil"]); r += 1
    add_row(r, "IAT °C", vars_["iat"]); r += 1
    add_row(r, "MAF kg/h", vars_["maf"]); r += 1
    add_row(r, "Battery V", vars_["vbatt"]); r += 1
    add_row(r, "Load % (approx)", vars_["load"]); r += 1
    add_row(r, "Throttle raw", vars_["thr"]); r += 1
    add_row(r, "Throttle2 raw", vars_["thr2"]); r += 1

    ttk.Label(frm, textvariable=vars_["timeouts"]).grid(row=r, column=0, columnspan=2, sticky="w", pady=(8, 0)); r += 1
    ttk.Label(frm, textvariable=vars_["status"]).grid(row=r, column=0, columnspan=2, sticky="w"); r += 1
    ttk.Label(frm, textvariable=vars_["lasterr"], foreground="gray").grid(row=r, column=0, columnspan=2, sticky="w")

    # Smoothing
    ema_rpm = EMA(alpha=max(0.0, min(1.0, args.rpm_alpha)))
    ta = max(0.0, min(1.0, args.temp_alpha))
    ema_cool = EMA(alpha=ta)
    ema_oil = EMA(alpha=ta)
    ema_iat = EMA(alpha=min(0.35, ta + 0.05))  # slightly more smoothing for IAT (optional)

    # Scheduling
    period = 1.0 / max(args.hz, 0.2)
    period_ms = max(10, int(period * 1000))
    next_t = time.time() + period

    timeout_count = 0

    def tick():
        nonlocal next_t, timeout_count

        try:
            resp = d.send(REQ_GENERAL)

            # base decoded values
            g = decode_general(resp)

            # derived channels from your logs
            maf_kgph = u16be(resp, 8) / 10.0
            vbatt_v = resp[23] / 10.0
            load_pct = resp[19] / 2.55  # approx until fully confirmed/scaled
            thr_raw = resp[6]
            thr2_raw = resp[7]

            # apply smoothing
            rpm = int(round(ema_rpm.update(float(g.rpm))))
            cool = ema_cool.update(g.coolant_c)
            oil = ema_oil.update(g.oil_c)
            iat = ema_iat.update(g.iat_c)

            # update UI
            vars_["rpm"].set(f"{rpm:d}")
            vars_["cool"].set(f"{cool:0.1f}")
            vars_["oil"].set(f"{oil:0.1f}")
            vars_["iat"].set(f"{iat:0.1f}")
            vars_["maf"].set(f"{maf_kgph:0.1f}")
            vars_["vbatt"].set(f"{vbatt_v:0.1f}")
            vars_["load"].set(f"{load_pct:0.1f}")
            vars_["thr"].set(f"{thr_raw:d}")
            vars_["thr2"].set(f"{thr2_raw:d}")

            vars_["status"].set("OK")
            vars_["lasterr"].set("")

            if log_w:
                log_w.writerow(
                    [time.time(), g.rpm, g.coolant_c, g.oil_c, g.iat_c, maf_kgph, vbatt_v, load_pct, thr_raw, thr2_raw]
                    + list(resp[:32])
                )
                log_f.flush()

        except TimeoutError as e:
            timeout_count += 1
            vars_["timeouts"].set(f"Timeouts: {timeout_count}")
            vars_["status"].set("ERR: timeout")
            vars_["lasterr"].set(str(e))

        except Exception as e:
            vars_["status"].set("ERR")
            vars_["lasterr"].set(str(e))

        # stable scheduler (avoid drift)
        now = time.time()
        delay = next_t - now
        next_t += period
        root.after(max(1, int(max(0.0, delay) * 1000)), tick)

    def on_close():
        try:
            if log_f:
                log_f.close()
        finally:
            d.close()
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.after(150, tick)
    root.mainloop()


if __name__ == "__main__":
    main()
