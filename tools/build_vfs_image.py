#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор образа файловой системы LittleFS v2 (vfs_widgets.bin) для ESP32-2432S028.
Записывается по адресу 0x343000 (раздел vfs, 189 блоков по 4096 байт).
При старте автоматически читает JSON-конфигурацию пользователя (Wi-Fi, город, выбранный виджет,
тип экрана и пин подсветки) из блока 160 раздела vfs (физический адрес флеш-памяти 0x3E3000).
"""

import os
from littlefs import LittleFS

BOOT_PY = """# boot.py — ESP32-2432S028 (CYD)
import gc
gc.collect()
"""

MAIN_PY = """# main.py — ESP32-2432S028 (CYD 2.8" 320x240) 10 Clocks, Calendars, Weather + Diagnostics
import os
import gc
import sys
import time
import json
import select
import machine
import lvgl as lv
import lcd_bus
import ili9341
import xpt2046
import task_handler

print("CYD_BOOT_START: Mounting config from 0x3E3000...")

cfg = {
    "cydVariant": "standard",
    "wifiSsid": "",
    "wifiPassword": "",
    "cityEn": "Moscow",
    "latitude": 55.7558,
    "longitude": 37.6173,
    "timezoneOffset": 3,
    "selectedWidget": "v1_classic_cal",
    "notes": ["Morning coffee & warmup", "Check daily tasks", "Evening walk 19:00"],
    "eventTitle": "NEW YEAR",
    "eventDays": "73 DAYS",
    "tempC": 14,
    "windMs": 3.5
}

try:
    from flashbdev import bdev
    raw = bytearray(4096)
    bdev.readblocks(160, raw)
    if raw[:8] == b"CYDCFG1:":
        end_idx = raw.find(b"\\x00", 8)
        if end_idx > 8:
            loaded = json.loads(bytes(raw[8:end_idx]).decode("utf-8"))
            for k in loaded:
                cfg[k] = loaded[k]
            print("CYD_CONFIG_LOADED:", cfg.get("selectedWidget"), cfg.get("cydVariant"))
except Exception as e:
    print("CYD_CONFIG_DEFAULT:", e)

variant = str(cfg.get("cydVariant", "standard"))
# Профили экранов разных ревизий CYD (ESP32-2432S028 / S024 / 2USB V3)
bl_pin = 21
init_type = 1
rot_hex = 0x20
use_bgr = True
byte_swap = 1

if variant == "variant2":
    # Ревизия 2USB (ESP32-D0WD-V3 с Type-C + Micro-USB, драйвер Type 2)
    bl_pin = 21
    init_type = 2
    rot_hex = 0xE0
    use_bgr = False
elif variant == "variant3_type2_bgr":
    # Ревизия V3 с Type 2 и порядком цветов BGR
    bl_pin = 21
    init_type = 2
    rot_hex = 0x20
    use_bgr = True
elif variant == "variant4_bl27":
    # Ревизия с подсветкой на GPIO 27 (ESP32-2432S024 / S035)
    bl_pin = 27
    init_type = 1
    rot_hex = 0x20
    use_bgr = True

print("CYD_DISPLAY_INIT: bl_pin={}, init_type={}, rot={}".format(bl_pin, init_type, hex(rot_hex)))

spi_bus = machine.SPI.Bus(host=1, mosi=13, miso=12, sck=14)
display_bus = lcd_bus.SPIBus(spi_bus=spi_bus, freq=24000000, dc=2, cs=15)

display = ili9341.ILI9341(
    data_bus=display_bus,
    display_width=320,
    display_height=240,
    backlight_pin=bl_pin,
    backlight_on_state=ili9341.STATE_PWM,
    color_space=lv.COLOR_FORMAT.RGB565,
    color_byte_order=ili9341.BYTE_ORDER_BGR if use_bgr else ili9341.BYTE_ORDER_RGB,
    rgb565_byte_swap=byte_swap
)

display._ORIENTATION_TABLE = (rot_hex, 0x0, 0x0, 0x0)
display.set_rotation(lv.DISPLAY_ROTATION._0)
display.set_power(True)
display.init(init_type)
display.set_backlight(100)

indev_bus = machine.SPI.Bus(host=2, mosi=32, miso=39, sck=25)
indev_dev = machine.SPI.Device(spi_bus=indev_bus, freq=2000000, cs=33)
indev = xpt2046.XPT2046(device=indev_dev)

th = task_handler.TaskHandler()

WIFI_SSID = str(cfg.get("wifiSsid", ""))
WIFI_PASS = str(cfg.get("wifiPassword", ""))
CITY_NAME = str(cfg.get("cityEn", "Moscow"))
CITY_LAT = float(cfg.get("latitude", 55.7558))
CITY_LON = float(cfg.get("longitude", 37.6173))
TZ_OFFSET = int(float(cfg.get("timezoneOffset", 3)) * 3600)
START_WIDGET = str(cfg.get("selectedWidget", "v1_classic_cal"))
AUTO_CAROUSEL = (START_WIDGET == "v10_carousel")
NOTES_LIST = cfg.get("notes", ["Task 1", "Task 2", "Task 3"])
EVENT_TITLE = str(cfg.get("eventTitle", "NEW YEAR"))
EVENT_DAYS = str(cfg.get("eventDays", "73 DAYS"))

state = {
    "temp": float(cfg.get("tempC", 14)),
    "wind": float(cfg.get("windMs", 3.5)),
    "hum": 64,
    "tmax": float(cfg.get("tempC", 14)) + 3,
    "tmin": float(cfg.get("tempC", 14)) - 2,
    "wifi_ok": False,
    "pomo_sec": 25 * 60,
    "pomo_run": False,
    "ticks": 0
}

MODES = [
    "v1_classic_cal",
    "v2_flip_clock",
    "v3_tear_cal",
    "v4_weather_pro",
    "v5_day_planner",
    "v6_world_clock",
    "v7_countdown",
    "v8_pomodoro",
    "v9_night_clock"
]

current_idx = 0
if START_WIDGET in MODES:
    current_idx = MODES.index(START_WIDGET)

DAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS_EN = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]

scr = lv.screen_active()
scr.set_style_bg_color(lv.color_hex(0x070B14), 0)
scr.set_style_bg_opa(255, 0)
scr.remove_flag(lv.obj.FLAG.SCROLLABLE)

top = lv.obj(scr)
top.remove_style_all()
top.set_size(320, 24)
top.set_pos(0, 0)
top.set_style_bg_color(lv.color_hex(0x101C33), 0)
top.set_style_bg_opa(255, 0)

lbl_top_left = lv.label(top)
lbl_top_left.set_text("1/9 CLASSIC CALENDAR")
lbl_top_left.set_style_text_color(lv.color_hex(0x00E5FF), 0)
lbl_top_left.set_style_text_font(lv.font_montserrat_12, 0)
lbl_top_left.align(lv.ALIGN.LEFT_MID, 8, 0)

lbl_top_right = lv.label(top)
lbl_top_right.set_text(CITY_NAME[:14])
lbl_top_right.set_style_text_color(lv.color_hex(0x10B981), 0)
lbl_top_right.set_style_text_font(lv.font_montserrat_12, 0)
lbl_top_right.align(lv.ALIGN.RIGHT_MID, -8, 0)

body = lv.obj(scr)
body.remove_style_all()
body.set_size(320, 182)
body.set_pos(0, 24)

nav = lv.obj(scr)
nav.remove_style_all()
nav.set_size(320, 34)
nav.set_pos(0, 206)
nav.set_style_bg_color(lv.color_hex(0x0E172A), 0)
nav.set_style_bg_opa(255, 0)

def get_dt():
    t = time.localtime(time.time() + TZ_OFFSET)
    if t[0] < 2025:
        return (2026, 10, 19, 14, 30, t[5], 0, 292)
    return t

def fmt_temp(v):
    return ("+{:.0f} C" if v > 0 else "{:.0f} C").format(v)

def days_in_month(y, m):
    dm = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    if m == 2 and ((y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)):
        return 29
    return dm[(m - 1) % 12]

def dow_mon_first(y, m, d):
    t_tbl = (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)
    if m < 3:
        y -= 1
    w = (y + y // 4 - y // 100 + y // 400 + t_tbl[m - 1] + d) % 7
    return (w + 6) % 7

def build_v1():
    lbl_top_left.set_text("1/9 CLASSIC CALENDAR")
    t = get_dt()

    left = lv.obj(body)
    left.remove_style_all()
    left.set_size(132, 174)
    left.set_pos(6, 4)

    clk = lv.label(left)
    clk.set_text("{:02d}:{:02d}".format(t[3], t[4]))
    clk.set_style_text_font(lv.font_montserrat_36, 0)
    clk.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    clk.set_pos(2, 2)

    dt_l = lv.label(left)
    dt_l.set_text("{}\\n{:02d}.{:02d}.{:04d}".format(DAYS_EN[t[6] % 7], t[2], t[1], t[0]))
    dt_l.set_style_text_font(lv.font_montserrat_12, 0)
    dt_l.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    dt_l.set_pos(4, 46)

    wb = lv.obj(left)
    wb.remove_style_all()
    wb.set_size(126, 80)
    wb.set_pos(2, 86)
    wb.set_style_bg_color(lv.color_hex(0x111E36), 0)
    wb.set_style_bg_opa(255, 0)
    wb.set_style_radius(8, 0)

    wl = lv.label(wb)
    wl.set_text("{}\\n{}\\nWind {:.1f} m/s".format(CITY_NAME[:14], fmt_temp(state["temp"]), state["wind"]))
    wl.set_style_text_font(lv.font_montserrat_14, 0)
    wl.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    wl.align(lv.ALIGN.CENTER, 0, 0)

    cbox = lv.obj(body)
    cbox.remove_style_all()
    cbox.set_size(174, 170)
    cbox.set_pos(140, 6)
    cbox.set_style_bg_color(lv.color_hex(0x0D1526), 0)
    cbox.set_style_bg_opa(255, 0)
    cbox.set_style_radius(8, 0)

    mhdr = lv.label(cbox)
    mhdr.set_text("{} {}".format(MONTHS_EN[(t[1]-1)%12], t[0]))
    mhdr.set_style_text_font(lv.font_montserrat_12, 0)
    mhdr.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    mhdr.align(lv.ALIGN.TOP_MID, 0, 4)

    dhdr = lv.label(cbox)
    dhdr.set_text("Mo Tu We Th Fr Sa Su")
    dhdr.set_style_text_font(lv.font_montserrat_12, 0)
    dhdr.set_style_text_color(lv.color_hex(0x94A3B8), 0)
    dhdr.set_pos(10, 22)

    first_col = dow_mon_first(t[0], t[1], 1)
    tot_days = days_in_month(t[0], t[1])
    r = 0
    c = first_col
    for d in range(1, tot_days + 1):
        x = 10 + c * 22
        y = 40 + r * 20
        if d == t[2]:
            hl = lv.obj(cbox)
            hl.remove_style_all()
            hl.set_size(20, 16)
            hl.set_pos(x - 2, y - 1)
            hl.set_style_bg_color(lv.color_hex(0x00E5FF), 0)
            hl.set_style_bg_opa(255, 0)
            hl.set_style_radius(4, 0)
        dl = lv.label(cbox)
        dl.set_text("{:2d}".format(d))
        dl.set_style_text_font(lv.font_montserrat_12, 0)
        if d == t[2]:
            dl.set_style_text_color(lv.color_hex(0x000000), 0)
        elif c >= 5:
            dl.set_style_text_color(lv.color_hex(0xFB7185), 0)
        else:
            dl.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        dl.set_pos(x, y)
        c += 1
        if c >= 7:
            c = 0
            r += 1

def build_v2():
    lbl_top_left.set_text("2/9 GIANT FLIP CLOCK")
    t = get_dt()
    for i, val in enumerate((t[3], t[4])):
        card = lv.obj(body)
        card.remove_style_all()
        card.set_size(136, 118)
        card.set_pos(16 + i * 152, 10)
        card.set_style_bg_color(lv.color_hex(0x142038), 0)
        card.set_style_bg_opa(255, 0)
        card.set_style_radius(14, 0)
        lbl = lv.label(card)
        lbl.set_text("{:02d}".format(val))
        lbl.set_style_text_font(lv.font_montserrat_48, 0)
        lbl.set_style_text_color(lv.color_hex(0x00E5FF if i == 0 else 0xFFFFFF), 0)
        lbl.center()

    sub = lv.label(body)
    sub.set_text("{} {:02d} {}  |  {} {}".format(DAYS_EN[t[6] % 7], t[2], MONTHS_EN[(t[1]-1)%12][:3], CITY_NAME[:12], fmt_temp(state["temp"])))
    sub.set_style_text_font(lv.font_montserrat_16, 0)
    sub.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    sub.align(lv.ALIGN.BOTTOM_MID, 0, -12)

def build_v3():
    lbl_top_left.set_text("3/9 TEAR-OFF DAY CALENDAR")
    t = get_dt()
    sheet = lv.obj(body)
    sheet.remove_style_all()
    sheet.set_size(154, 164)
    sheet.set_pos(12, 9)
    sheet.set_style_bg_color(lv.color_hex(0xF8FAFC), 0)
    sheet.set_style_bg_opa(255, 0)
    sheet.set_style_radius(12, 0)

    hdr = lv.obj(sheet)
    hdr.remove_style_all()
    hdr.set_size(154, 34)
    hdr.set_pos(0, 0)
    hdr.set_style_bg_color(lv.color_hex(0xEF4444), 0)
    hdr.set_style_bg_opa(255, 0)

    mh = lv.label(hdr)
    mh.set_text("{} {}".format(MONTHS_EN[(t[1]-1)%12], t[0]))
    mh.set_style_text_font(lv.font_montserrat_14, 0)
    mh.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    mh.center()

    dl = lv.label(sheet)
    dl.set_text(str(t[2]))
    dl.set_style_text_font(lv.font_montserrat_48, 0)
    dl.set_style_text_color(lv.color_hex(0x0F172A), 0)
    dl.align(lv.ALIGN.CENTER, 0, 4)

    wl = lv.label(sheet)
    wl.set_text(DAYS_EN[t[6] % 7].upper())
    wl.set_style_text_font(lv.font_montserrat_14, 0)
    wl.set_style_text_color(lv.color_hex(0x475569), 0)
    wl.align(lv.ALIGN.BOTTOM_MID, 0, -10)

    rpanel = lv.obj(body)
    rpanel.remove_style_all()
    rpanel.set_size(134, 164)
    rpanel.set_pos(176, 9)
    rpanel.set_style_bg_color(lv.color_hex(0x101C33), 0)
    rpanel.set_style_bg_opa(255, 0)
    rpanel.set_style_radius(12, 0)

    rt = lv.label(rpanel)
    rt.set_text("{:02d}:{:02d}\\n\\n{}\\n{}\\nWind {:.1f}m/s".format(t[3], t[4], CITY_NAME[:12], fmt_temp(state["temp"]), state["wind"]))
    rt.set_style_text_font(lv.font_montserrat_18, 0)
    rt.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    rt.align(lv.ALIGN.CENTER, 0, 0)

def build_v4():
    lbl_top_left.set_text("4/9 WEATHER STATION")
    t = get_dt()
    card = lv.obj(body)
    card.remove_style_all()
    card.set_size(300, 164)
    card.align(lv.ALIGN.CENTER, 0, 0)
    card.set_style_bg_color(lv.color_hex(0x101C33), 0)
    card.set_style_bg_opa(255, 0)
    card.set_style_radius(12, 0)

    c1 = lv.label(card)
    c1.set_text("{}   |   {:02d}:{:02d}".format(CITY_NAME, t[3], t[4]))
    c1.set_style_text_font(lv.font_montserrat_18, 0)
    c1.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    c1.set_pos(14, 12)

    c2 = lv.label(card)
    c2.set_text(fmt_temp(state["temp"]))
    c2.set_style_text_font(lv.font_montserrat_48, 0)
    c2.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    c2.set_pos(14, 42)

    c3 = lv.label(card)
    c3.set_text("Max: {}  Min: {}\\nWind: {:.1f} m/s   Humidity: {}%".format(
        fmt_temp(state["tmax"]), fmt_temp(state["tmin"]), state["wind"], state["hum"]
    ))
    c3.set_style_text_font(lv.font_montserrat_14, 0)
    c3.set_style_text_color(lv.color_hex(0x10B981), 0)
    c3.set_pos(14, 108)

def build_v5():
    lbl_top_left.set_text("5/9 DAILY PLANNER")
    t = get_dt()
    hdr = lv.label(body)
    hdr.set_text("{:02d}:{:02d}  |  {:02d}.{:02d}  |  {} {}".format(t[3], t[4], t[2], t[1], CITY_NAME[:10], fmt_temp(state["temp"])))
    hdr.set_style_text_font(lv.font_montserrat_18, 0)
    hdr.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    hdr.set_pos(12, 10)

    for i, note in enumerate(NOTES_LIST[:3]):
        row = lv.obj(body)
        row.remove_style_all()
        row.set_size(296, 38)
        row.set_pos(12, 42 + i * 44)
        row.set_style_bg_color(lv.color_hex(0x111E36), 0)
        row.set_style_bg_opa(255, 0)
        row.set_style_radius(8, 0)
        nl = lv.label(row)
        nl.set_text("[{}] {}".format(i + 1, str(note)[:32]))
        nl.set_style_text_font(lv.font_montserrat_14, 0)
        nl.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        nl.align(lv.ALIGN.LEFT_MID, 12, 0)

def build_v6():
    lbl_top_left.set_text("6/9 WORLD CLOCK (3 ZONES)")
    t_local = get_dt()
    utc_h = (t_local[3] - int(TZ_OFFSET // 3600)) % 24
    tok_h = (utc_h + 9) % 24

    zones = [
        (CITY_NAME[:12], t_local[3], t_local[4], 0x00E5FF),
        ("London / UTC", utc_h, t_local[4], 0x10B981),
        ("Tokyo (JST)", tok_h, t_local[4], 0xFBBF24)
    ]
    for i, (zname, zh, zm, col) in enumerate(zones):
        box = lv.obj(body)
        box.remove_style_all()
        box.set_size(296, 48)
        box.set_pos(12, 10 + i * 56)
        box.set_style_bg_color(lv.color_hex(0x111E36), 0)
        box.set_style_bg_opa(255, 0)
        box.set_style_radius(10, 0)

        zn = lv.label(box)
        zn.set_text(zname)
        zn.set_style_text_font(lv.font_montserrat_16, 0)
        zn.set_style_text_color(lv.color_hex(col), 0)
        zn.align(lv.ALIGN.LEFT_MID, 14, 0)

        zv = lv.label(box)
        zv.set_text("{:02d}:{:02d}".format(zh, zm))
        zv.set_style_text_font(lv.font_montserrat_28, 0)
        zv.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        zv.align(lv.ALIGN.RIGHT_MID, -14, 0)

def build_v7():
    lbl_top_left.set_text("7/9 EVENT COUNTDOWN")
    t = get_dt()
    card = lv.obj(body)
    card.remove_style_all()
    card.set_size(296, 162)
    card.align(lv.ALIGN.CENTER, 0, 0)
    card.set_style_bg_color(lv.color_hex(0x111E36), 0)
    card.set_style_bg_opa(255, 0)
    card.set_style_radius(14, 0)

    l1 = lv.label(card)
    l1.set_text(EVENT_TITLE.upper())
    l1.set_style_text_font(lv.font_montserrat_18, 0)
    l1.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    l1.align(lv.ALIGN.TOP_MID, 0, 16)

    l2 = lv.label(card)
    l2.set_text(EVENT_DAYS)
    l2.set_style_text_font(lv.font_montserrat_44, 0)
    l2.set_style_text_color(lv.color_hex(0x10B981), 0)
    l2.align(lv.ALIGN.CENTER, 0, 2)

    l3 = lv.label(card)
    l3.set_text("Now: {:02d}:{:02d}  |  {} {}".format(t[3], t[4], CITY_NAME[:10], fmt_temp(state["temp"])))
    l3.set_style_text_font(lv.font_montserrat_14, 0)
    l3.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    l3.align(lv.ALIGN.BOTTOM_MID, 0, -14)

def build_v8():
    lbl_top_left.set_text("8/9 POMODORO & CLOCK")
    t = get_dt()
    mins = state["pomo_sec"] // 60
    secs = state["pomo_sec"] % 60

    pl = lv.label(body)
    pl.set_text("{:02d}:{:02d}".format(mins, secs))
    pl.set_style_text_font(lv.font_montserrat_48, 0)
    pl.set_style_text_color(lv.color_hex(0xF59E0B), 0)
    pl.align(lv.ALIGN.TOP_MID, 0, 14)

    btn1 = lv.button(body)
    btn1.set_size(120, 42)
    btn1.set_pos(30, 82)
    b1l = lv.label(btn1)
    b1l.set_text("PAUSE" if state["pomo_run"] else "START")
    b1l.center()
    def toggle_p(e):
        state["pomo_run"] = not state["pomo_run"]
        render_current()
    btn1.add_event_cb(toggle_p, lv.EVENT.CLICKED, None)

    btn2 = lv.button(body)
    btn2.set_size(120, 42)
    btn2.set_pos(170, 82)
    b2l = lv.label(btn2)
    b2l.set_text("RESET 25:00")
    b2l.center()
    def reset_p(e):
        state["pomo_run"] = False
        state["pomo_sec"] = 25 * 60
        render_current()
    btn2.add_event_cb(reset_p, lv.EVENT.CLICKED, None)

    cl = lv.label(body)
    cl.set_text("Clock: {:02d}:{:02d}  |  {} {}".format(t[3], t[4], CITY_NAME[:10], fmt_temp(state["temp"])))
    cl.set_style_text_font(lv.font_montserrat_14, 0)
    cl.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    cl.align(lv.ALIGN.BOTTOM_MID, 0, -12)

def build_v9():
    lbl_top_left.set_text("9/9 NIGHT AMBER CLOCK")
    t = get_dt()
    nc = lv.label(body)
    nc.set_text("{:02d}:{:02d}".format(t[3], t[4]))
    nc.set_style_text_font(lv.font_montserrat_48, 0)
    nc.set_style_text_color(lv.color_hex(0xFFB000), 0)
    nc.align(lv.ALIGN.CENTER, 0, -20)

    nd = lv.label(body)
    nd.set_text("{} {:02d}.{:02d}.{:04d}  |  {}".format(DAYS_EN[t[6] % 7], t[2], t[1], t[0], fmt_temp(state["temp"])))
    nd.set_style_text_font(lv.font_montserrat_16, 0)
    nd.set_style_text_color(lv.color_hex(0xB45309), 0)
    nd.align(lv.ALIGN.CENTER, 0, 36)

BUILDERS = (
    build_v1, build_v2, build_v3, build_v4, build_v5,
    build_v6, build_v7, build_v8, build_v9
)

def render_current():
    try:
        body.clean()
        BUILDERS[current_idx % len(BUILDERS)]()
    except Exception as e:
        err_lbl = lv.label(body)
        err_lbl.set_text("UI note: " + str(e))
        err_lbl.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        err_lbl.center()

btn_prev = lv.button(nav)
btn_prev.set_size(88, 26)
btn_prev.align(lv.ALIGN.LEFT_MID, 8, 0)
lp = lv.label(btn_prev)
lp.set_text("< PREV")
lp.set_style_text_font(lv.font_montserrat_12, 0)
lp.center()

lbl_nav_mid = lv.label(nav)
lbl_nav_mid.set_text("TOUCH TO SWITCH")
lbl_nav_mid.set_style_text_font(lv.font_montserrat_10, 0)
lbl_nav_mid.set_style_text_color(lv.color_hex(0x94A3B8), 0)
lbl_nav_mid.align(lv.ALIGN.CENTER, 0, 0)

btn_next = lv.button(nav)
btn_next.set_size(88, 26)
btn_next.align(lv.ALIGN.RIGHT_MID, -8, 0)
ln = lv.label(btn_next)
ln.set_text("NEXT >")
ln.set_style_text_font(lv.font_montserrat_12, 0)
ln.center()

def on_prev(e):
    global current_idx
    current_idx = (current_idx - 1) % len(BUILDERS)
    render_current()

def on_next(e):
    global current_idx
    current_idx = (current_idx + 1) % len(BUILDERS)
    render_current()

btn_prev.add_event_cb(on_prev, lv.EVENT.CLICKED, None)
btn_next.add_event_cb(on_next, lv.EVENT.CLICKED, None)

render_current()

def print_diag_report():
    try:
        rep = {
            "status": "SCREEN_ACTIVE",
            "release": os.uname().release,
            "machine": os.uname().machine,
            "mem_free_kb": gc.mem_free() // 1024,
            "variant": variant,
            "bl_pin": bl_pin,
            "init_type": init_type,
            "widget": START_WIDGET,
            "files": os.listdir("/")
        }
        print("CYD_SCAN_REPORT:" + json.dumps(rep))
    except Exception as e:
        print("CYD_SCAN_ERROR:", e)

print_diag_report()

def connect_wifi_and_fetch():
    if not WIFI_SSID:
        return
    try:
        import network
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if not wlan.isconnected():
            lbl_top_right.set_text("Wi-Fi...")
            wlan.connect(WIFI_SSID, WIFI_PASS)
            for _ in range(20):
                if wlan.isconnected():
                    break
                time.sleep_ms(200)
        if wlan.isconnected():
            state["wifi_ok"] = True
            lbl_top_right.set_text(CITY_NAME[:10] + " OK")
            try:
                import ntptime
                ntptime.settime()
            except Exception:
                pass
            try:
                import urequests
                url = "http://api.open-meteo.com/v1/forecast?latitude={}&longitude={}&current_weather=true".format(CITY_LAT, CITY_LON)
                r = urequests.get(url)
                data = r.json()
                r.close()
                if "current_weather" in data:
                    t_now = data["current_weather"].get("temperature", state["temp"])
                    state["temp"] = t_now
                    state["tmax"] = t_now + 3
                    state["tmin"] = t_now - 2
                    state["wind"] = data["current_weather"].get("windspeed", state["wind"])
            except Exception:
                pass
            render_current()
        else:
            lbl_top_right.set_text(CITY_NAME[:12])
    except Exception:
        pass

connect_wifi_and_fetch()

poll_in = select.poll()
poll_in.register(sys.stdin, select.POLLIN)
s_buf = ""

def tick_cb(t):
    global current_idx, s_buf
    if state["pomo_run"] and state["pomo_sec"] > 0:
        state["pomo_sec"] -= 1
        if current_idx == 7:
            render_current()
    state["ticks"] += 1
    if AUTO_CAROUSEL and state["ticks"] % 12 == 0:
        current_idx = (current_idx + 1) % len(BUILDERS)
        render_current()
    elif state["ticks"] % 30 == 0:
        render_current()

    while poll_in.poll(0):
        ch = sys.stdin.read(1)
        if not ch:
            break
        if ch in ("\\n", "\\r"):
            line = s_buf.strip()
            s_buf = ""
            if line == "SCAN":
                print_diag_report()
            elif line == "NEXT":
                current_idx = (current_idx + 1) % len(BUILDERS)
                render_current()
        else:
            s_buf += ch

timer_sec = lv.timer_create(tick_cb, 1000, None)
timer_sec.set_repeat_count(-1)
print("CYD_WIDGET_ENGINE_READY")
"""


def main():
    fs = LittleFS(block_size=4096, block_count=189, disk_version=0x00020000)
    with fs.open("/boot.py", "w") as f:
        f.write(BOOT_PY)
    with fs.open("/main.py", "w") as f:
        f.write(MAIN_PY)

    full_buf = bytes(fs.context.buffer)
    last_used_block = 0
    for b in range(189):
        chunk = full_buf[b * 4096 : (b + 1) * 4096]
        if chunk != b"\xff" * 4096:
            last_used_block = b

    trimmed_len = (last_used_block + 2) * 4096
    out_dir = os.path.join(os.path.dirname(__file__), "..", "public", "firmware")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "vfs_widgets.bin")
    with open(out_path, "wb") as f:
        f.write(full_buf[:trimmed_len])

    print(f"✅ Создан образ LittleFS v2: {out_path} ({trimmed_len} байт, последний блок: {last_used_block})")


if __name__ == "__main__":
    main()
