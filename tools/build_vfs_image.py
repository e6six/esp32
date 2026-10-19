#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор образа файловой системы LittleFS v2 (vfs_widgets.bin) для дисплея L i 435-2 4 (ESP32-2432S024R / S028).
Записывается по адресу 0x343000 (раздел vfs, 189 блоков по 4096 байт).
Особенности этой сборки:
1. 0% мерцания экрана: шина экрана SPI1 (пины 14, 13, 12, CS=15) используется ТОЛЬКО дисплеем.
2. Идеальная табличная вёрстка календаря (каждое число 1..31 стоит в собственной ячейке 26x24px с крупным шрифтом montserrat_16 и яркой подсветкой текущего дня!).
3. Увеличенные шрифты во всех 9 виджетах под компактный 2.4" экран 320x240 (используется вся высота экрана 240px без лишней нижней полосы).
4. Реальное время ПК (RTC) + живая погода Open-Meteo с сайта и по Wi-Fi.
"""

import os
from littlefs import LittleFS

BOOT_PY = """# boot.py — ESP32-2432S024R (L i 435-2 4)
import gc
import machine

# 1. Изолируем CS=33 и CS=5 в HIGH (1), чтобы на шине экрана SPI1 никогда не было помех и мерцания
try:
    machine.Pin(33, machine.Pin.OUT, value=1)
    machine.Pin(5, machine.Pin.OUT, value=1)
except Exception:
    pass

# 2. Гасим яркий красный RGB-светодиод (GPIO 4, 16, 17 — активный LOW: 1 = ВЫКЛ)
try:
    machine.Pin(4, machine.Pin.OUT, value=1)
    machine.Pin(16, machine.Pin.OUT, value=1)
    machine.Pin(17, machine.Pin.OUT, value=1)
except Exception:
    pass

gc.collect()
"""

DEFAULT_CFG_BYTES = (
    b'CYDCFG1:{"cydVariant":"s024_perfect","wifiSsid":"","wifiPassword":"",'
    b'"cityEn":"Moscow","latitude":55.7558,"longitude":37.6173,"timezoneOffset":3,'
    b'"selectedWidget":"v1_classic_cal","notes":["Morning coffee & warmup",'
    b'"Check daily tasks","Evening walk 19:00"],"eventTitle":"NEW YEAR",'
    b'"eventDays":"73 DAYS","tempC":14,"tmaxC":17,"tminC":11,"windMs":3.5,"humidity":64,'
    b'"rtcTuple":[2026,10,20,1,14,30,0]}\x00'
).ljust(2048, b" ")

MAIN_PY = """# main.py — ESP32-2432S024R (L i 435-2 4) Large-Font Desk Widgets & True Grid Calendar
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
import task_handler

# Фиксируем CS=33 и CS=5 в HIGH (1) — шина дисплея SPI1 работает на 100% чисто и без мерцания!
pin_touch_cs = machine.Pin(33, machine.Pin.OUT, value=1)
pin_sd_cs = machine.Pin(5, machine.Pin.OUT, value=1)
led_r = machine.Pin(4, machine.Pin.OUT, value=1)
led_g = machine.Pin(16, machine.Pin.OUT, value=1)
led_b = machine.Pin(17, machine.Pin.OUT, value=1)

print("CYD_BOOT_START: Loading configuration...")

cfg = {
    "cydVariant": "s024_perfect",
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
    "tmaxC": 17,
    "tminC": 11,
    "windMs": 3.5,
    "humidity": 64,
    "rtcTuple": [2026, 10, 20, 1, 14, 30, 0]
}

try:
    with open("/config.txt", "rb") as f:
        raw_file = f.read()
    if raw_file[:8] == b"CYDCFG1:":
        end_idx = raw_file.find(b"\\x00", 8)
        if end_idx > 8:
            loaded = json.loads(bytes(raw_file[8:end_idx]).decode("utf-8"))
            for k in loaded:
                cfg[k] = loaded[k]
            print("CYD_CONFIG_FILE_OK:", cfg.get("selectedWidget"), cfg.get("cydVariant"))
except Exception as e:
    print("CYD_CONFIG_FILE_ERR:", e)

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
except Exception:
    pass

rtc_synced_from_pc = False
try:
    rt = cfg.get("rtcTuple")
    if isinstance(rt, list) and len(rt) >= 7:
        machine.RTC().datetime((int(rt[0]), int(rt[1]), int(rt[2]), int(rt[3]), int(rt[4]), int(rt[5]), int(rt[6]), 0))
        rtc_synced_from_pc = True
except Exception:
    pass

variant = str(cfg.get("cydVariant", "s024_perfect"))

bl_pin = 27
aux_bl_pin = 21
rot_hex = 0x60
use_bgr = False
inv_cmd = 0x20
byte_swap = 1
spi_freq = 16000000

if variant in ("s024_perfect", "variant4_bl27", "standard"):
    rot_hex = 0x60
    use_bgr = False
    inv_cmd = 0x20
elif variant == "s024_bgr_inv0":
    rot_hex = 0x60
    use_bgr = True
    inv_cmd = 0x20
elif variant in ("bl27_st7789", "s024_rgb_inv1"):
    rot_hex = 0x60
    use_bgr = False
    inv_cmd = 0x21
elif variant in ("bl27_type2_e0", "s024_bgr_inv1"):
    rot_hex = 0x60
    use_bgr = True
    inv_cmd = 0x21

try:
    machine.Pin(aux_bl_pin, machine.Pin.OUT, value=1)
except Exception:
    pass

gc.collect()
spi_bus = machine.SPI.Bus(host=1, mosi=13, miso=12, sck=14)
display_bus = lcd_bus.SPIBus(spi_bus=spi_bus, freq=spi_freq, dc=2, cs=15)

display = ili9341.ILI9341(
    data_bus=display_bus,
    display_width=320,
    display_height=240,
    backlight_pin=bl_pin,
    backlight_on_state=ili9341.STATE_HIGH,
    color_space=lv.COLOR_FORMAT.RGB565,
    color_byte_order=ili9341.BYTE_ORDER_BGR if use_bgr else ili9341.BYTE_ORDER_RGB,
    rgb565_byte_swap=byte_swap
)

display._ORIENTATION_TABLE = (rot_hex, 0x0, 0x0, 0x0)
display.set_power(True)

display.set_params(0x01)
time.sleep_ms(120)
display.set_params(0x11)
time.sleep_ms(120)
display.set_params(0x3A, bytearray([0x55]))
mad_val = rot_hex | (0x08 if use_bgr else 0x00)
display.set_params(0x36, bytearray([mad_val]))
display.set_params(0xB2, bytearray([0x0C, 0x0C, 0x00, 0x33, 0x33]))
display.set_params(0xB7, bytearray([0x35]))
display.set_params(0xBB, bytearray([0x19]))
display.set_params(0xC0, bytearray([0x2C]))
display.set_params(0xC2, bytearray([0x01]))
display.set_params(0xC3, bytearray([0x12]))
display.set_params(0xC4, bytearray([0x20]))
display.set_params(0xC6, bytearray([0x0F]))
display.set_params(0xD0, bytearray([0xA4, 0xA1]))
display.set_params(inv_cmd)
display.set_params(0x13)
time.sleep_ms(20)
display.set_params(0x29)
time.sleep_ms(50)
display._initilized = True

display.set_rotation(lv.DISPLAY_ROTATION._0)
display.set_params(0x36, bytearray([mad_val]))
display.set_params(inv_cmd)
display.set_backlight(100)
try:
    machine.Pin(27, machine.Pin.OUT, value=1)
    machine.Pin(21, machine.Pin.OUT, value=1)
except Exception:
    pass

# Кнопка BOOT (GPIO 0) на задней стороне платы — для мгновенного переключения виджетов на самой плате
btn_boot = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)

th = task_handler.TaskHandler()

WIFI_SSID = str(cfg.get("wifiSsid", "")).strip()
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
    "tmax": float(cfg.get("tmaxC", float(cfg.get("tempC", 14)) + 3)),
    "tmin": float(cfg.get("tminC", float(cfg.get("tempC", 14)) - 2)),
    "wind": float(cfg.get("windMs", 3.5)),
    "hum": int(cfg.get("humidity", 64)),
    "wifi_ok": False,
    "wifi_connecting": False,
    "wifi_synced": False,
    "ntp_applied": False,
    "pomo_sec": 25 * 60,
    "pomo_run": True,
    "ticks": 0,
    "last_min": -1
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
DAYS_SHORT = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
MONTHS_EN = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]

# Используем ВСЕ 320x240 пикселей экрана (компактная шапка 22px + просторная рабочая область 320x218px!)
scr = lv.screen_active()
scr.set_style_bg_color(lv.color_hex(0x070B14), 0)
scr.set_style_bg_opa(255, 0)
scr.remove_flag(lv.obj.FLAG.SCROLLABLE)

top = lv.obj(scr)
top.remove_style_all()
top.set_size(320, 22)
top.set_pos(0, 0)
top.set_style_bg_color(lv.color_hex(0x101C33), 0)
top.set_style_bg_opa(255, 0)

lbl_top_left = lv.label(top)
lbl_top_left.set_text("1/9 CALENDAR & CLOCK")
lbl_top_left.set_style_text_color(lv.color_hex(0x00E5FF), 0)
lbl_top_left.set_style_text_font(lv.font_montserrat_12, 0)
lbl_top_left.align(lv.ALIGN.LEFT_MID, 8, 0)

lbl_top_right = lv.label(top)
lbl_top_right.set_text(CITY_NAME[:12] + (" • OK" if rtc_synced_from_pc else ""))
lbl_top_right.set_style_text_color(lv.color_hex(0x10B981), 0)
lbl_top_right.set_style_text_font(lv.font_montserrat_12, 0)
lbl_top_right.align(lv.ALIGN.RIGHT_MID, -8, 0)

body = lv.obj(scr)
body.remove_style_all()
body.set_size(320, 218)
body.set_pos(0, 22)

def get_dt():
    if state["ntp_applied"]:
        t = time.localtime(time.time() + TZ_OFFSET)
    else:
        t = time.localtime()
    if t[0] < 2025:
        return (2026, 10, 20, 14, 30, t[5], 1, 293)
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

pomo_lbl_ref = None

# 1. КЛАССИЧЕСКИЙ КАЛЕНДАРЬ + КРУПНЫЕ ЧАСЫ И ПОГОДА (РОВНАЯ ТАБЛИЧНАЯ СЕТКА ДНЕЙ!)
def build_v1():
    lbl_top_left.set_text("1/9 CALENDAR & WEATHER")
    t = get_dt()

    # Левая панель (118 x 210): крупные часы + дата + карточка погоды с крупной температурой
    left = lv.obj(body)
    left.remove_style_all()
    left.set_size(120, 210)
    left.set_pos(4, 4)

    clk = lv.label(left)
    clk.set_text("{:02d}:{:02d}".format(t[3], t[4]))
    clk.set_style_text_font(lv.font_montserrat_40, 0)
    clk.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    clk.set_pos(2, 2)

    day_lbl = lv.label(left)
    day_lbl.set_text(DAYS_EN[t[6] % 7])
    day_lbl.set_style_text_font(lv.font_montserrat_16, 0)
    day_lbl.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    day_lbl.set_pos(4, 48)

    dt_lbl = lv.label(left)
    dt_lbl.set_text("{:02d}.{:02d}.{:04d}".format(t[2], t[1], t[0]))
    dt_lbl.set_style_text_font(lv.font_montserrat_16, 0)
    dt_lbl.set_style_text_color(lv.color_hex(0xCBD5E1), 0)
    dt_lbl.set_pos(4, 68)

    wb = lv.obj(left)
    wb.remove_style_all()
    wb.set_size(116, 114)
    wb.set_pos(2, 94)
    wb.set_style_bg_color(lv.color_hex(0x111E36), 0)
    wb.set_style_bg_opa(255, 0)
    wb.set_style_radius(10, 0)

    w_city = lv.label(wb)
    w_city.set_text(CITY_NAME[:11])
    w_city.set_style_text_font(lv.font_montserrat_14, 0)
    w_city.set_style_text_color(lv.color_hex(0x94A3B8), 0)
    w_city.align(lv.ALIGN.TOP_MID, 0, 8)

    w_temp = lv.label(wb)
    w_temp.set_text(fmt_temp(state["temp"]))
    w_temp.set_style_text_font(lv.font_montserrat_28, 0)
    w_temp.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    w_temp.align(lv.ALIGN.CENTER, 0, 2)

    w_wind = lv.label(wb)
    w_wind.set_text("Wind {:.1f} m/s".format(state["wind"]))
    w_wind.set_style_text_font(lv.font_montserrat_14, 0)
    w_wind.set_style_text_color(lv.color_hex(0x10B981), 0)
    w_wind.align(lv.ALIGN.BOTTOM_MID, 0, -8)

    # Правая панель (190 x 210): ИДЕАЛЬНО РОВНАЯ СЕТКА КАЛЕНДАРЯ (7 колонок по 26px!)
    cbox = lv.obj(body)
    cbox.remove_style_all()
    cbox.set_size(190, 210)
    cbox.set_pos(126, 4)
    cbox.set_style_bg_color(lv.color_hex(0x0D1526), 0)
    cbox.set_style_bg_opa(255, 0)
    cbox.set_style_radius(10, 0)

    mhdr = lv.label(cbox)
    mhdr.set_text("{} {}".format(MONTHS_EN[(t[1]-1)%12], t[0]))
    mhdr.set_style_text_font(lv.font_montserrat_16, 0)
    mhdr.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    mhdr.align(lv.ALIGN.TOP_MID, 0, 6)

    # Шапка дней недели: каждая ячейка строго 26px шириной
    for col_i, dname in enumerate(DAYS_SHORT):
        hcell = lv.obj(cbox)
        hcell.remove_style_all()
        hcell.set_size(26, 20)
        hcell.set_pos(4 + col_i * 26, 30)
        hl = lv.label(hcell)
        hl.set_text(dname)
        hl.set_style_text_font(lv.font_montserrat_14, 0)
        hl.set_style_text_color(lv.color_hex(0xFB7185 if col_i >= 5 else 0x94A3B8), 0)
        hl.center()

    # Числа месяца: каждое число в собственной ровной ячейке 26x25px со шрифтом montserrat_16!
    first_col = dow_mon_first(t[0], t[1], 1)
    tot_days = days_in_month(t[0], t[1])
    row_h = 25 if (first_col + tot_days) > 35 else 28
    r_idx = 0
    c_idx = first_col

    for d in range(1, tot_days + 1):
        cell = lv.obj(cbox)
        cell.remove_style_all()
        cell.set_size(25, row_h - 2)
        cell.set_pos(4 + c_idx * 26, 52 + r_idx * row_h)

        is_today = (d == t[2])
        if is_today:
            cell.set_style_bg_color(lv.color_hex(0x00E5FF), 0)
            cell.set_style_bg_opa(255, 0)
            cell.set_style_radius(6, 0)

        dl = lv.label(cell)
        dl.set_text(str(d))
        dl.set_style_text_font(lv.font_montserrat_16, 0)
        if is_today:
            dl.set_style_text_color(lv.color_hex(0x070B14), 0)
        elif c_idx >= 5:
            dl.set_style_text_color(lv.color_hex(0xFB7185), 0)
        else:
            dl.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        dl.center()

        c_idx += 1
        if c_idx >= 7:
            c_idx = 0
            r_idx += 1

# 2. ГИГАНТСКИЕ FLIP-ЧАСЫ НА ВЕСЬ ЭКРАН + ДАТА И ПОГОДА
def build_v2():
    lbl_top_left.set_text("2/9 GIANT FLIP CLOCK")
    t = get_dt()
    for i, val in enumerate((t[3], t[4])):
        card = lv.obj(body)
        card.remove_style_all()
        card.set_size(144, 144)
        card.set_pos(12 + i * 152, 10)
        card.set_style_bg_color(lv.color_hex(0x142038), 0)
        card.set_style_bg_opa(255, 0)
        card.set_style_radius(16, 0)
        lbl = lv.label(card)
        lbl.set_text("{:02d}".format(val))
        lbl.set_style_text_font(lv.font_montserrat_48, 0)
        lbl.set_style_text_color(lv.color_hex(0x00E5FF if i == 0 else 0xFFFFFF), 0)
        lbl.center()

    sub = lv.label(body)
    sub.set_text("{} {:02d} {}  •  {} {}".format(DAYS_EN[t[6] % 7], t[2], MONTHS_EN[(t[1]-1)%12][:3], CITY_NAME[:10], fmt_temp(state["temp"])))
    sub.set_style_text_font(lv.font_montserrat_18, 0)
    sub.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    sub.align(lv.ALIGN.BOTTOM_MID, 0, -14)

# 3. ОТРЫВНОЙ КАЛЕНДАРЬ ДНЯ + КРУПНЫЕ ЧАСЫ И ПОГОДА
def build_v3():
    lbl_top_left.set_text("3/9 TEAR-OFF DAY CALENDAR")
    t = get_dt()
    sheet = lv.obj(body)
    sheet.remove_style_all()
    sheet.set_size(156, 198)
    sheet.set_pos(10, 10)
    sheet.set_style_bg_color(lv.color_hex(0xF8FAFC), 0)
    sheet.set_style_bg_opa(255, 0)
    sheet.set_style_radius(12, 0)

    hdr = lv.obj(sheet)
    hdr.remove_style_all()
    hdr.set_size(156, 40)
    hdr.set_pos(0, 0)
    hdr.set_style_bg_color(lv.color_hex(0xEF4444), 0)
    hdr.set_style_bg_opa(255, 0)

    mh = lv.label(hdr)
    mh.set_text("{} {}".format(MONTHS_EN[(t[1]-1)%12], t[0]))
    mh.set_style_text_font(lv.font_montserrat_16, 0)
    mh.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    mh.center()

    dl = lv.label(sheet)
    dl.set_text(str(t[2]))
    dl.set_style_text_font(lv.font_montserrat_48, 0)
    dl.set_style_text_color(lv.color_hex(0x0F172A), 0)
    dl.align(lv.ALIGN.CENTER, 0, 4)

    wl = lv.label(sheet)
    wl.set_text(DAYS_EN[t[6] % 7].upper())
    wl.set_style_text_font(lv.font_montserrat_16, 0)
    wl.set_style_text_color(lv.color_hex(0x334155), 0)
    wl.align(lv.ALIGN.BOTTOM_MID, 0, -12)

    rpanel = lv.obj(body)
    rpanel.remove_style_all()
    rpanel.set_size(136, 198)
    rpanel.set_pos(174, 10)
    rpanel.set_style_bg_color(lv.color_hex(0x101C33), 0)
    rpanel.set_style_bg_opa(255, 0)
    rpanel.set_style_radius(12, 0)

    r_clk = lv.label(rpanel)
    r_clk.set_text("{:02d}:{:02d}".format(t[3], t[4]))
    r_clk.set_style_text_font(lv.font_montserrat_36, 0)
    r_clk.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    r_clk.align(lv.ALIGN.TOP_MID, 0, 18)

    r_city = lv.label(rpanel)
    r_city.set_text(CITY_NAME[:11])
    r_city.set_style_text_font(lv.font_montserrat_16, 0)
    r_city.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    r_city.align(lv.ALIGN.CENTER, 0, -4)

    r_tmp = lv.label(rpanel)
    r_tmp.set_text(fmt_temp(state["temp"]))
    r_tmp.set_style_text_font(lv.font_montserrat_32, 0)
    r_tmp.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    r_tmp.align(lv.ALIGN.CENTER, 0, 34)

    r_wnd = lv.label(rpanel)
    r_wnd.set_text("Wind {:.1f} m/s".format(state["wind"]))
    r_wnd.set_style_text_font(lv.font_montserrat_14, 0)
    r_wnd.set_style_text_color(lv.color_hex(0x10B981), 0)
    r_wnd.align(lv.ALIGN.BOTTOM_MID, 0, -14)

# 4. МЕТЕОСТАНЦИЯ PRO (КРУПНЫЕ ДАННЫЕ ПОГОДЫ И ЧАСЫ)
def build_v4():
    lbl_top_left.set_text("4/9 WEATHER STATION PRO")
    t = get_dt()
    card = lv.obj(body)
    card.remove_style_all()
    card.set_size(304, 200)
    card.align(lv.ALIGN.CENTER, 0, 0)
    card.set_style_bg_color(lv.color_hex(0x101C33), 0)
    card.set_style_bg_opa(255, 0)
    card.set_style_radius(14, 0)

    c1 = lv.label(card)
    c1.set_text("{}   •   {:02d}:{:02d}".format(CITY_NAME[:12], t[3], t[4]))
    c1.set_style_text_font(lv.font_montserrat_24, 0)
    c1.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    c1.set_pos(16, 14)

    c2 = lv.label(card)
    c2.set_text(fmt_temp(state["temp"]))
    c2.set_style_text_font(lv.font_montserrat_48, 0)
    c2.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    c2.set_pos(16, 54)

    c3 = lv.label(card)
    c3.set_text("Max: {}    Min: {}\\nWind: {:.1f} m/s    Humidity: {}%".format(
        fmt_temp(state["tmax"]), fmt_temp(state["tmin"]), state["wind"], state["hum"]
    ))
    c3.set_style_text_font(lv.font_montserrat_18, 0)
    c3.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    c3.set_pos(16, 128)

# 5. ЕЖЕДНЕВНИК ЗАДАЧ + ВРЕМЯ И ПОГОДА
def build_v5():
    lbl_top_left.set_text("5/9 DAILY PLANNER")
    t = get_dt()
    hdr = lv.label(body)
    hdr.set_text("{:02d}:{:02d}  •  {:02d}.{:02d}  •  {} {}".format(t[3], t[4], t[2], t[1], CITY_NAME[:9], fmt_temp(state["temp"])))
    hdr.set_style_text_font(lv.font_montserrat_20, 0)
    hdr.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    hdr.set_pos(12, 10)

    for i, note in enumerate(NOTES_LIST[:3]):
        row = lv.obj(body)
        row.remove_style_all()
        row.set_size(296, 48)
        row.set_pos(12, 44 + i * 54)
        row.set_style_bg_color(lv.color_hex(0x111E36), 0)
        row.set_style_bg_opa(255, 0)
        row.set_style_radius(10, 0)
        nl = lv.label(row)
        nl.set_text("{}. {}".format(i + 1, str(note)[:28]))
        nl.set_style_text_font(lv.font_montserrat_16, 0)
        nl.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        nl.align(lv.ALIGN.LEFT_MID, 14, 0)

# 6. МИРОВОЕ ВРЕМЯ (3 ЧАСОВЫХ ПОЯСА КРУПНЫМ ШРИФТОМ)
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
        box.set_size(296, 60)
        box.set_pos(12, 10 + i * 68)
        box.set_style_bg_color(lv.color_hex(0x111E36), 0)
        box.set_style_bg_opa(255, 0)
        box.set_style_radius(12, 0)

        zn = lv.label(box)
        zn.set_text(zname)
        zn.set_style_text_font(lv.font_montserrat_20, 0)
        zn.set_style_text_color(lv.color_hex(col), 0)
        zn.align(lv.ALIGN.LEFT_MID, 14, 0)

        zv = lv.label(box)
        zv.set_text("{:02d}:{:02d}".format(zh, zm))
        zv.set_style_text_font(lv.font_montserrat_32, 0)
        zv.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        zv.align(lv.ALIGN.RIGHT_MID, -14, 0)

# 7. ОБРАТНЫЙ ОТСЧЁТ ДО СОБЫТИЯ
def build_v7():
    lbl_top_left.set_text("7/9 EVENT COUNTDOWN")
    t = get_dt()
    card = lv.obj(body)
    card.remove_style_all()
    card.set_size(296, 198)
    card.align(lv.ALIGN.CENTER, 0, 0)
    card.set_style_bg_color(lv.color_hex(0x111E36), 0)
    card.set_style_bg_opa(255, 0)
    card.set_style_radius(14, 0)

    l1 = lv.label(card)
    l1.set_text(EVENT_TITLE.upper())
    l1.set_style_text_font(lv.font_montserrat_24, 0)
    l1.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    l1.align(lv.ALIGN.TOP_MID, 0, 18)

    l2 = lv.label(card)
    l2.set_text(EVENT_DAYS)
    l2.set_style_text_font(lv.font_montserrat_48, 0)
    l2.set_style_text_color(lv.color_hex(0x10B981), 0)
    l2.align(lv.ALIGN.CENTER, 0, 0)

    l3 = lv.label(card)
    l3.set_text("{:02d}:{:02d}  •  {} {}".format(t[3], t[4], CITY_NAME[:10], fmt_temp(state["temp"])))
    l3.set_style_text_font(lv.font_montserrat_18, 0)
    l3.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    l3.align(lv.ALIGN.BOTTOM_MID, 0, -16)

# 8. ФОКУС-ТАЙМЕР ПОМОДОРО + ЧАСЫ
def build_v8():
    global pomo_lbl_ref
    lbl_top_left.set_text("8/9 POMODORO TIMER")
    t = get_dt()
    mins = state["pomo_sec"] // 60
    secs = state["pomo_sec"] % 60

    pl = lv.label(body)
    pl.set_text("{:02d}:{:02d}".format(mins, secs))
    pl.set_style_text_font(lv.font_montserrat_48, 0)
    pl.set_style_text_color(lv.color_hex(0xF59E0B), 0)
    pl.align(lv.ALIGN.TOP_MID, 0, 18)
    pomo_lbl_ref = pl

    badge = lv.obj(body)
    badge.remove_style_all()
    badge.set_size(240, 46)
    badge.align(lv.ALIGN.CENTER, 0, 14)
    badge.set_style_bg_color(lv.color_hex(0x142038), 0)
    badge.set_style_bg_opa(255, 0)
    badge.set_style_radius(10, 0)
    bl = lv.label(badge)
    bl.set_text("FOCUS 25 MIN ACTIVE")
    bl.set_style_text_font(lv.font_montserrat_18, 0)
    bl.set_style_text_color(lv.color_hex(0x10B981), 0)
    bl.center()

    cl = lv.label(body)
    cl.set_text("Clock: {:02d}:{:02d}  •  {} {}".format(t[3], t[4], CITY_NAME[:10], fmt_temp(state["temp"])))
    cl.set_style_text_font(lv.font_montserrat_18, 0)
    cl.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    cl.align(lv.ALIGN.BOTTOM_MID, 0, -16)

# 9. НОЧНЫЕ ЯНТАРНЫЕ ЧАСЫ
def build_v9():
    lbl_top_left.set_text("9/9 NIGHT AMBER CLOCK")
    t = get_dt()
    nc = lv.label(body)
    nc.set_text("{:02d}:{:02d}".format(t[3], t[4]))
    nc.set_style_text_font(lv.font_montserrat_48, 0)
    nc.set_style_text_color(lv.color_hex(0xFFB000), 0)
    nc.align(lv.ALIGN.CENTER, 0, -24)

    nd = lv.label(body)
    nd.set_text("{} {:02d}.{:02d}.{:04d}".format(DAYS_EN[t[6] % 7], t[2], t[1], t[0]))
    nd.set_style_text_font(lv.font_montserrat_20, 0)
    nd.set_style_text_color(lv.color_hex(0xF59E0B), 0)
    nd.align(lv.ALIGN.CENTER, 0, 28)

    nw = lv.label(body)
    nw.set_text("{}  •  {}  •  {:.1f} m/s".format(CITY_NAME[:12], fmt_temp(state["temp"]), state["wind"]))
    nw.set_style_text_font(lv.font_montserrat_16, 0)
    nw.set_style_text_color(lv.color_hex(0xB45309), 0)
    nw.align(lv.ALIGN.BOTTOM_MID, 0, -18)

BUILDERS = (
    build_v1, build_v2, build_v3, build_v4, build_v5,
    build_v6, build_v7, build_v8, build_v9
)

def render_current():
    global pomo_lbl_ref
    try:
        pomo_lbl_ref = None
        gc.collect()
        body.clean()
        t_now = get_dt()
        state["last_min"] = t_now[4]
        BUILDERS[current_idx % len(BUILDERS)]()
        gc.collect()
    except Exception as e:
        print("RENDER_ERR:", e)

render_current()

def print_diag_report():
    try:
        rep = {
            "status": "SCREEN_ACTIVE",
            "board": "ESP32-2432S024R (L i 435-2 4)",
            "release": os.uname().release,
            "mem_free_kb": gc.mem_free() // 1024,
            "variant": variant,
            "bl_pin": bl_pin,
            "rot": hex(rot_hex),
            "inv": hex(inv_cmd),
            "wifi_ok": state["wifi_ok"],
            "widget": MODES[current_idx % len(MODES)]
        }
        print("CYD_SCAN_REPORT:" + json.dumps(rep))
    except Exception as e:
        print("CYD_SCAN_ERROR:", e)

print_diag_report()

# Опрос кнопки BOOT (GPIO 0) и мгновенных USB-команд с сайта (NEXT / PREV / SET:...) каждые 80 мс
boot_hold_cnt = 0
poll_in = select.poll()
poll_in.register(sys.stdin, select.POLLIN)
s_buf = ""

def poll_controls(t):
    global current_idx, boot_hold_cnt, s_buf, AUTO_CAROUSEL
    # 1. Физическая кнопка BOOT (GPIO 0) на плате
    try:
        if btn_boot.value() == 0:
            boot_hold_cnt += 1
            if boot_hold_cnt == 2:
                led_g.value(0)
                current_idx = (current_idx + 1) % len(BUILDERS)
                render_current()
                led_g.value(1)
        else:
            boot_hold_cnt = 0
    except Exception:
        pass

    # 2. Мгновенные команды переключения по USB с сайта (за 0.05 сек без перепрошивки!)
    try:
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
                elif line == "PREV":
                    current_idx = (current_idx - 1) % len(BUILDERS)
                    render_current()
                elif line.startswith("SET:"):
                    w_id = line[4:].strip()
                    if w_id == "v10_carousel":
                        AUTO_CAROUSEL = True
                    else:
                        AUTO_CAROUSEL = False
                        if w_id in MODES:
                            current_idx = MODES.index(w_id)
                            render_current()
            else:
                s_buf += ch
    except Exception:
        pass

timer_btn = lv.timer_create(poll_controls, 80, None)
timer_btn.set_repeat_count(-1)

wlan = None

def start_wifi_nonblocking():
    global wlan
    if not WIFI_SSID:
        return
    try:
        import network
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if not wlan.isconnected():
            lbl_top_right.set_text("Wi-Fi...")
            wlan.connect(WIFI_SSID, WIFI_PASS)
            state["wifi_connecting"] = True
    except Exception as e:
        print("WIFI_START_ERR:", e)

def sync_ntp_and_weather():
    try:
        import ntptime
        ntptime.settime()
        state["ntp_applied"] = True
    except Exception:
        pass

    for proto in ("http", "https"):
        try:
            import urequests
            url = "{}://api.open-meteo.com/v1/forecast?latitude={}&longitude={}&current_weather=true".format(
                proto, CITY_LAT, CITY_LON
            )
            r = urequests.get(url)
            data = r.json()
            r.close()
            if "current_weather" in data:
                t_now = float(data["current_weather"].get("temperature", state["temp"]))
                state["temp"] = t_now
                state["tmax"] = t_now + 3
                state["tmin"] = t_now - 2
                state["wind"] = float(data["current_weather"].get("windspeed", state["wind"]))
                break
        except Exception:
            pass

    lbl_top_right.set_text("WIFI OK " + fmt_temp(state["temp"]))
    render_current()

def tick_cb(t):
    global current_idx
    state["ticks"] += 1

    if state["ticks"] == 1 and WIFI_SSID:
        start_wifi_nonblocking()
    elif state["wifi_connecting"] and not state["wifi_synced"] and wlan is not None:
        try:
            if wlan.isconnected():
                state["wifi_ok"] = True
                state["wifi_synced"] = True
                state["wifi_connecting"] = False
                sync_ntp_and_weather()
            elif state["ticks"] > 25:
                state["wifi_connecting"] = False
                lbl_top_right.set_text(CITY_NAME[:10] + " • OK")
        except Exception:
            pass
    elif state["wifi_synced"] and state["ticks"] % 900 == 0 and wlan is not None:
        try:
            if wlan.isconnected():
                sync_ntp_and_weather()
        except Exception:
            pass

    if state["pomo_run"] and state["pomo_sec"] > 0:
        state["pomo_sec"] -= 1
        if current_idx == 7 and pomo_lbl_ref is not None:
            try:
                pomo_lbl_ref.set_text("{:02d}:{:02d}".format(state["pomo_sec"] // 60, state["pomo_sec"] % 60))
            except Exception:
                pass
    elif state["pomo_run"] and state["pomo_sec"] == 0:
        state["pomo_sec"] = 25 * 60

    t_now = get_dt()
    if AUTO_CAROUSEL and state["ticks"] % 15 == 0:
        current_idx = (current_idx + 1) % len(BUILDERS)
        render_current()
    elif t_now[4] != state["last_min"]:
        render_current()

timer_sec = lv.timer_create(tick_cb, 1000, None)
timer_sec.set_repeat_count(-1)
print("CYD_WIDGET_ENGINE_READY")
"""


def main():
    fs = LittleFS(block_size=4096, block_count=189, disk_version=0x00020000)
    with fs.open("/boot.py", "w") as f:
        f.write(BOOT_PY)
    with fs.open("/config.txt", "wb") as f:
        f.write(DEFAULT_CFG_BYTES)
    with fs.open("/main.py", "w") as f:
        f.write(MAIN_PY)

    full_buf = bytes(fs.context.buffer)
    cfg_idx = full_buf.find(b"CYDCFG1:")
    print(f"📍 Метка CYDCFG1: внутри vfs_widgets.bin по смещению {cfg_idx} (блок {cfg_idx // 4096}, смещение в блоке {cfg_idx % 4096})")
    assert cfg_idx != -1 and (cfg_idx % 4096) + 2048 <= 4096

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
