# mslive/apps/dash_pygame.py
from __future__ import annotations

import argparse
import csv
import time

import pygame

from mslive.decoders.ms42_general import decode_general
from mslive.util.cli import add_common_args, add_port_or_replay, open_ds2_or_exit, resolve_log_path_from_args

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
    add_port_or_replay(ap)
    add_common_args(ap, default_baud=9600, default_hz=10.0)

    # smoothing knobs (default: NO rpm smoothing)
    ap.add_argument("--rpm-alpha", type=float, default=1.0, help="1.0=no smoothing, 0.2=heavy smoothing")
    ap.add_argument("--temp-alpha", type=float, default=0.25, help="smoothing for temps (0..1)")

    ap.add_argument("--log", default=None, help="output csv path (default: logs/ms42_dash_YYYYmmdd_HHMMSS.csv)")
    ap.add_argument("--replay-speed", type=float, default=1.0)

    args = ap.parse_args()

    if args.replay:
        from mslive.core.replay import ReplayDS2, ReplayConfig
        d = ReplayDS2(
            ReplayConfig(
                csv_path=args.replay,
                realtime=True,
                loop=True,
                speed=args.replay_speed,
            )
        )
        d.open()
    else:
        d = open_ds2_or_exit(port=args.port, baud=args.baud, debug=args.debug)
        d.initialized = True

    log_path = resolve_log_path_from_args(args, "log", "dash")
    log_f = open(log_path, "w", newline="", encoding="utf-8")
    log_w = csv.writer(log_f)
    log_w.writerow(
        ["ts", "rpm", "coolant_c", "oil_c", "iat_c", "maf_kgph", "vbatt_v", "load_pct", "thr_raw", "thr2_raw"]
        + [f"b{i}" for i in range(32)]
    )
    log_f.flush()

    pygame.init()
    pygame.display.set_caption("MS42 Live")
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    clock = pygame.time.Clock()

    font_label = pygame.font.SysFont("DejaVu Sans", 26, bold=True)
    font_value = pygame.font.SysFont("DejaVu Sans Mono", 36)
    font_status = pygame.font.SysFont("DejaVu Sans", 20)

    vars_ = {
        "rpm": "—",
        "cool": "—",
        "oil": "—",
        "iat": "—",
        "maf": "—",
        "vbatt": "—",
        "load": "—",
        "thr": "—",
        "thr2": "—",
        "status": "Connected",
        "timeouts": "Timeouts: 0",
        "lasterr": "",
    }

    rows = [
        ("RPM", "rpm"),
        ("Coolant °C", "cool"),
        ("Oil °C", "oil"),
        ("IAT °C", "iat"),
        ("MAF kg/h", "maf"),
        ("Battery V", "vbatt"),
        ("Load % (approx)", "load"),
        ("Throttle raw", "thr"),
        ("Throttle2 raw", "thr2"),
    ]

    # Smoothing
    ema_rpm = EMA(alpha=max(0.0, min(1.0, args.rpm_alpha)))
    ta = max(0.0, min(1.0, args.temp_alpha))
    ema_cool = EMA(alpha=ta)
    ema_oil = EMA(alpha=ta)
    ema_iat = EMA(alpha=min(0.35, ta + 0.05))  # slightly more smoothing for IAT (optional)

    # Scheduling
    period = 1.0 / max(args.hz, 0.2)
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
            vars_["rpm"] = f"{rpm:d}"
            vars_["cool"] = f"{cool:0.1f}"
            vars_["oil"] = f"{oil:0.1f}"
            vars_["iat"] = f"{iat:0.1f}"
            vars_["maf"] = f"{maf_kgph:0.1f}"
            vars_["vbatt"] = f"{vbatt_v:0.1f}"
            vars_["load"] = f"{load_pct:0.1f}"
            vars_["thr"] = f"{thr_raw:d}"
            vars_["thr2"] = f"{thr2_raw:d}"

            vars_["status"] = "OK"
            vars_["lasterr"] = ""

            if log_w:
                log_w.writerow(
                    [time.time(), g.rpm, g.coolant_c, g.oil_c, g.iat_c, maf_kgph, vbatt_v, load_pct, thr_raw, thr2_raw]
                    + list(resp[:32])
                )
                log_f.flush()

        except TimeoutError as e:
            timeout_count += 1
            vars_["timeouts"] = f"Timeouts: {timeout_count}"
            vars_["status"] = "ERR: timeout"
            vars_["lasterr"] = str(e)

        except Exception as e:
            vars_["status"] = "ERR"
            vars_["lasterr"] = str(e)

        # stable scheduler (avoid drift)
        now = time.time()
        while next_t <= now:
            next_t += period

    def draw_text(text: str, font: pygame.font.Font, color: tuple[int, int, int], x: int, y: int, align_right: bool = False):
        surf = font.render(text, True, color)
        rect = surf.get_rect()
        if align_right:
            rect.topright = (x, y)
        else:
            rect.topleft = (x, y)
        screen.blit(surf, rect)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        now = time.time()
        if now >= next_t:
            tick()

        screen.fill((18, 18, 20))

        left_x = 36
        right_x = 990
        y = 26
        row_gap = 58

        for label, key in rows:
            draw_text(label, font_label, (230, 230, 230), left_x, y)
            draw_text(vars_[key], font_value, (245, 245, 245), right_x, y - 8, align_right=True)
            y += row_gap

        y += 8
        draw_text(vars_["timeouts"], font_status, (200, 200, 200), left_x, y)
        y += 26
        draw_text(vars_["status"], font_status, (200, 200, 200), left_x, y)
        y += 26
        if vars_["lasterr"]:
            draw_text(vars_["lasterr"], font_status, (140, 140, 140), left_x, y)

        pygame.display.flip()
        clock.tick(30)

    try:
        if log_f:
            log_f.close()
    finally:
        d.close()
        pygame.quit()

if __name__ == "__main__":
    main()
