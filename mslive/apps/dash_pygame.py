# mslive/apps/dash_pygame.py
from __future__ import annotations

import argparse
import csv
import time

import pygame

from mslive.decoders.ms42_general import decode_general
from mslive.util.cli import add_common_args, add_port_or_replay, open_ds2_or_exit, resolve_log_path_from_args

REQ_GENERAL = bytes.fromhex("12 05 0B 03")

COOL_YELLOW = 105.0
COOL_RED = 110.0
OIL_YELLOW = 120.0
OIL_RED = 125.0

COL_BG = (18, 18, 20)
COL_TEXT = (245, 245, 245)
COL_DIM = (170, 170, 170)
COL_YELLOW = (255, 210, 70)
COL_RED = (255, 80, 80)
COL_TILE_BG = (26, 26, 30)
COL_TILE_BORDER = (40, 40, 46)


def u16be(resp: bytes, i: int) -> int:
    return (resp[i] << 8) | resp[i + 1]

def temp_color(value_c: float, yellow: float, red: float) -> tuple[int, int, int]:
    if value_c >= red:
        return COL_RED
    if value_c >= yellow:
        return COL_YELLOW
    return COL_TEXT

def temp_bg_color(value_c: float, yellow: float, red: float) -> tuple[int, int, int]:
    if value_c >= red:
        return COL_RED
    if value_c >= yellow:
        return COL_YELLOW
    return COL_TILE_BG


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
    ap.add_argument("--no-log", action="store_true", help="disable CSV logging")
    ap.add_argument("--replay-speed", type=float, default=1.0)
    ap.add_argument("--loop", action=argparse.BooleanOptionalAction, default=True, help="loop replay when used")

    args = ap.parse_args()

    if args.replay:
        from mslive.core.replay import ReplayDS2, ReplayConfig
        d = ReplayDS2(
            ReplayConfig(
                csv_path=args.replay,
                realtime=True,
                loop=args.loop,
                speed=args.replay_speed,
            )
        )
        d.open()
    else:
        d = open_ds2_or_exit(port=args.port, baud=args.baud, debug=args.debug)
        d.initialized = True

    log_f = None
    log_w = None
    if not args.no_log and (not args.replay or args.log is not None):
        log_path = resolve_log_path_from_args(args, "log", "dash")
        log_f = open(log_path, "w", newline="", encoding="utf-8")
        log_w = csv.writer(log_f)
        log_w.writerow(
            ["ts", "rpm", "coolant_c", "oil_c", "iat_c", "ign_deg_kw", "maf_kgph", "vbatt_v", "load_pct", "thr_raw", "thr2_raw"]
            + [f"b{i}" for i in range(32)]
        )
        log_f.flush()

    pygame.init()
    pygame.display.set_caption("MS42 Live")
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    clock = pygame.time.Clock()

    font_label = pygame.font.SysFont("DejaVu Sans", 28, bold=True)
    font_value = pygame.font.SysFont("DejaVu Sans Mono", 40)
    font_status = pygame.font.SysFont("DejaVu Sans", 22)

    page = 1  # 1..3

    vars_ = {
        "rpm": "—",
        "cool": "—",
        "oil": "—",
        "iat": "—",
        "ign": "—",
        "maf": "—",
        "vbatt": "—",
        "load": "—",
        "thr": "—",
        "thr2": "—",
        "status": "Connected",
        "timeouts": "Timeouts: 0",
        "lasterr": "",
    }

    live = {
        "cool": None,
        "oil": None,
        "iat": None,
        "vbatt": None,
        "rpm": None,
        "ign": None,
        "resp": None,
    }

    rows = [
        ("RPM", "rpm"),
        ("Coolant °C", "cool"),
        ("Oil °C", "oil"),
        ("IAT °C", "iat"),
        ("Ign °KW", "ign"),
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
            ign = g.ign_deg_kw

            # update UI
            vars_["rpm"] = f"{rpm:d}"
            vars_["cool"] = f"{cool:0.1f}"
            vars_["oil"] = f"{oil:0.1f}"
            vars_["iat"] = f"{iat:0.1f}"
            vars_["ign"] = f"{ign:0.1f}"
            vars_["maf"] = f"{maf_kgph:0.1f}"
            vars_["vbatt"] = f"{vbatt_v:0.1f}"
            vars_["load"] = f"{load_pct:0.1f}"
            vars_["thr"] = f"{thr_raw:d}"
            vars_["thr2"] = f"{thr2_raw:d}"

            live["rpm"] = rpm
            live["cool"] = cool
            live["oil"] = oil
            live["iat"] = iat
            live["vbatt"] = vbatt_v
            live["ign"] = ign
            live["resp"] = resp

            vars_["status"] = "OK"
            vars_["lasterr"] = ""

            if log_w:
                log_w.writerow(
                    [time.time(), g.rpm, g.coolant_c, g.oil_c, g.iat_c, g.ign_deg_kw, maf_kgph, vbatt_v, load_pct, thr_raw, thr2_raw]
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

    def draw_text_center(text: str, font: pygame.font.Font, color: tuple[int, int, int], x: int, y: int):
        surf = font.render(text, True, color)
        rect = surf.get_rect()
        rect.center = (x, y)
        screen.blit(surf, rect)

    def draw_tile(title: str, value: str, x: int, y: int, w: int, h: int,
                  value_color: tuple[int, int, int] = COL_TEXT,
                  bg_color: tuple[int, int, int] = COL_TILE_BG,
                  overlay_text: str | None = None):
        pygame.draw.rect(screen, bg_color, (x, y, w, h), border_radius=16)
        pygame.draw.rect(screen, COL_TILE_BORDER, (x, y, w, h), width=2, border_radius=16)
        draw_text(title, font_label, COL_DIM, x + 18, y + 14)
        draw_text(value, font_value, value_color, x + w - 18, y + 56, align_right=True)
        if overlay_text:
            draw_text_center(overlay_text, font_value, COL_BG, x + w // 2, y + h // 2)

    def nav_button_rects() -> tuple[pygame.Rect, pygame.Rect]:
        w = screen.get_width()
        pad = 16
        btn_w = 120
        btn_h = 32
        y = 8
        prev_rect = pygame.Rect(pad, y, btn_w, btn_h)
        next_rect = pygame.Rect(w - pad - btn_w, y, btn_w, btn_h)
        return prev_rect, next_rect

    def draw_nav_buttons(page_now: int, prev_rect: pygame.Rect, next_rect: pygame.Rect):
        pygame.draw.rect(screen, (28, 28, 32), prev_rect, border_radius=10)
        pygame.draw.rect(screen, (50, 50, 56), prev_rect, width=2, border_radius=10)
        draw_text_center("Prev", font_status, COL_TEXT, prev_rect.centerx, prev_rect.centery)

        pygame.draw.rect(screen, (28, 28, 32), next_rect, border_radius=10)
        pygame.draw.rect(screen, (50, 50, 56), next_rect, width=2, border_radius=10)
        draw_text_center("Next", font_status, COL_TEXT, next_rect.centerx, next_rect.centery)

        w = screen.get_width()
        draw_text_center(f"Page {page_now}/3", font_status, COL_DIM, w // 2, 24)

    running = True
    while running:
        prev_btn, next_btn = nav_button_rects()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key in (pygame.K_1,):
                    page = 1
                elif event.key in (pygame.K_2,):
                    page = 2
                elif event.key in (pygame.K_3,):
                    page = 3
                elif event.key in (pygame.K_SPACE, pygame.K_TAB):
                    page = 1 if page == 3 else page + 1
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if prev_btn.collidepoint(event.pos):
                    page = 3 if page == 1 else page - 1
                elif next_btn.collidepoint(event.pos):
                    page = 1 if page == 3 else page + 1

        now = time.time()
        if now >= next_t:
            tick()

        screen.fill(COL_BG)

        if page == 1:
            top_bar_h = 52
            pad = 24
            screen_w = screen.get_width()
            screen_h = screen.get_height()
            tile_w = (screen_w - pad * 3) // 2
            tile_h = 200
            x1 = pad
            x2 = pad * 2 + tile_w
            y1 = top_bar_h + pad
            y2 = y1 + pad + tile_h

            cool_col = COL_TEXT
            oil_col = COL_TEXT
            cool_bg = COL_TILE_BG
            oil_bg = COL_TILE_BG
            if live["cool"] is not None:
                cool_bg = temp_bg_color(live["cool"], COOL_YELLOW, COOL_RED)
            if live["oil"] is not None:
                oil_bg = temp_bg_color(live["oil"], OIL_YELLOW, OIL_RED)
            hot_cool = live["cool"] is not None and live["cool"] >= COOL_RED
            hot_oil = live["oil"] is not None and live["oil"] >= OIL_RED
            if cool_bg != COL_TILE_BG:
                cool_col = COL_BG
            if oil_bg != COL_TILE_BG:
                oil_col = COL_BG
            flash_hot = int(time.time() * 4) % 2 == 0

            draw_tile(
                "Oil °C",
                vars_["oil"],
                x1,
                y1,
                tile_w,
                tile_h,
                oil_col,
                oil_bg,
                "HOT" if hot_oil and flash_hot else None,
            )
            draw_tile(
                "Coolant °C",
                vars_["cool"],
                x2,
                y1,
                tile_w,
                tile_h,
                cool_col,
                cool_bg,
                "HOT" if hot_cool and flash_hot else None,
            )
            draw_tile("Battery V",  vars_["vbatt"], x1, y2, tile_w, tile_h, COL_TEXT)
            draw_tile("IAT °C",     vars_["iat"],  x2, y2, tile_w, tile_h, COL_TEXT)

            footer_y = y2 + tile_h + pad
            draw_text(
                f"RPM {vars_['rpm']}   Ign {vars_['ign']}°   {vars_['timeouts']}   {vars_['status']}",
                font_status,
                COL_DIM,
                24,
                footer_y,
            )

            # Hot indicators are now in-tile overlays.

        elif page == 2:
            left_x = 36
            right_x = screen.get_width() - 34
            screen_h = screen.get_height()
            top_bar_h = 52
            footer_block = 96
            y = top_bar_h + 8
            rows_area = max(100, screen_h - top_bar_h - footer_block)
            row_gap = rows_area / max(len(rows), 1)

            for label, key in rows:
                draw_text(label, font_label, (230, 230, 230), left_x, y)
                draw_text(vars_[key], font_value, (245, 245, 245), right_x, y - 8, align_right=True)
                y += row_gap

            y = top_bar_h + rows_area + 12
            draw_text(vars_["timeouts"], font_status, (200, 200, 200), left_x, y)
            y += 26
            draw_text(vars_["status"], font_status, (200, 200, 200), left_x, y)
            y += 26
            if vars_["lasterr"]:
                draw_text(vars_["lasterr"], font_status, (140, 140, 140), left_x, y)

        elif page == 3:
            left_x = 36
            y = 60
            draw_text("Status", font_label, COL_DIM, left_x, y)
            y += 34
            draw_text(vars_["status"], font_value, COL_TEXT, left_x, y)
            y += 52
            draw_text(vars_["timeouts"], font_status, COL_DIM, left_x, y)
            y += 30
            if vars_["lasterr"]:
                draw_text(vars_["lasterr"], font_status, (140, 140, 140), left_x, y)
                y += 30
            if live["resp"]:
                hexline = " ".join(f"{b:02X}" for b in live["resp"][:32])
                draw_text("b0..b31", font_label, COL_DIM, left_x, y + 16)
                draw_text(hexline, font_status, COL_TEXT, left_x, y + 42)

        draw_nav_buttons(page, prev_btn, next_btn)

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
