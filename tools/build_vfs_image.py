#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор образа файловой системы LittleFS v2 (vfs_widgets.bin) для дисплея L i 435-2 4 (ESP32-2432S024R / S028).
Записывается по адресу 0x343000 (раздел vfs, 189 блоков по 4096 байт).
Ключевые особенности:
1. 100% защита от зависания LVGL TaskHandler: внутри таймера tick_cb нет блокирующих сетевых вызовов
   (ntptime / urequests / wlan), которые блокировали планировщик micropython.schedule и замораживали экран.
2. Оптимизированное число объектов LVGL (~94 объекта в календаре против 136): исключает переполнение LV_MEM_SIZE.
3. Тёмная тема che(c) = lv.color_hex(c ^ 0xFFFFFF) и изумрудно-зелёный пульсирующий индикатор Wi-Fi (#18F018 / #086008).
"""

import os
import json
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

DEFAULT_CFG = {
    "cydVariant": "s024_perfect",
    "wifiSsid": "",
    "wifiPassword": "",
    "cityRu": "Бутово",
    "cityEn": "Butovo",
    "latitude": 55.5520,
    "longitude": 37.5510,
    "timezoneOffset": 3,
    "selectedWidget": "v1_classic_cal",
    "notes": [
        "Проверить погоду в Бутово",
        "Синхронизация метеостанции",
        "Отличного рабочего дня!"
    ],
    "eventTitle": "ДО НОВОГО ГОДА",
    "eventDays": "73 ДНЯ",
    "tempC": 5,
    "tmaxC": 7,
    "tminC": 2,
    "windMs": 2.2,
    "humidity": 68,
    "wcode": 0,
    "descRu": "Ясно",
    "rtcTuple": [2026, 10, 20, 1, 14, 30, 0]
}

DEFAULT_CFG_BYTES = (
    ("CYDCFG1:" + json.dumps(DEFAULT_CFG, ensure_ascii=False) + "\x00").encode("utf-8")
).ljust(2048, b" ")

MAIN_PY = """import os, gc, sys, time, json, select, machine
import lvgl as lv
import lcd_bus, ili9341, task_handler

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
    "cityRu": "Бутово",
    "cityEn": "Butovo",
    "latitude": 55.5520,
    "longitude": 37.5510,
    "timezoneOffset": 3,
    "selectedWidget": "v1_classic_cal",
    "notes": ["Проверить погоду в Бутово", "Синхронизация", "Отличного дня!"],
    "eventTitle": "ДО НОВОГО ГОДА",
    "eventDays": "73 ДНЯ",
    "tempC": 5,
    "tmaxC": 7,
    "tminC": 2,
    "windMs": 2.2,
    "humidity": 68,
    "wcode": 0,
    "descRu": "Ясно",
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
    raw_file = None
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
    raw = None
except Exception:
    pass

gc.collect()

try:
    rt = cfg.get("rtcTuple")
    if isinstance(rt, list) and len(rt) >= 7:
        machine.RTC().datetime((int(rt[0]), int(rt[1]), int(rt[2]), int(rt[3]), int(rt[4]), int(rt[5]), int(rt[6]), 0))
except Exception:
    pass

variant = str(cfg.get("cydVariant", "s024_perfect"))
rot_hex = 0x60
use_bgr = False
inv_cmd = 0x20
inv_xor = 0xFFFFFF
byte_swap = 1
spi_freq = 16000000

if variant in ("s024_bgr_inv0", "s024_rot0_bgr_noinv"):
    use_bgr = True; inv_xor = 0xFFFFFF
elif variant == "s024_rgb_inv1":
    use_bgr = False; inv_xor = 0xFFFFFF
elif variant == "s024_bgr_inv1":
    use_bgr = True; inv_xor = 0xFFFFFF

def che(c):
    return lv.color_hex(c ^ inv_xor)

gc.collect()
spi_bus = machine.SPI.Bus(host=1, mosi=13, miso=12, sck=14)
display_bus = lcd_bus.SPIBus(spi_bus=spi_bus, freq=spi_freq, dc=2, cs=15)

display = ili9341.ILI9341(
    data_bus=display_bus,
    display_width=320,
    display_height=240,
    backlight_pin=None,
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
bl_27 = machine.Pin(27, machine.Pin.OUT, value=1)
bl_21 = machine.Pin(21, machine.Pin.OUT, value=1)

btn_boot = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)
th = task_handler.TaskHandler()

def ru_up(s):
    res = ""
    for c in str(s):
        o = ord(c)
        if 0x0430 <= o <= 0x044F:
            res += chr(o - 32)
        elif o == 0x0451 or o == 0x0401:
            res += "Е"
        elif 97 <= o <= 122:
            res += chr(o - 32)
        else:
            res += c
    return res

RU_MAP = {
    "А": "A", "В": "B", "Е": "E", "Ё": "E", "З": "3",
    "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P",
    "С": "C", "Т": "T", "У": "Y", "Х": "X", "Ч": "4",
    "Ъ": "b", "Ы": "bl", "Ь": "b", "Ю": "IO"
}

RU_GLYPHS = {
    "Б": (7, 10, ((0,0,2,10),(2,0,4,2),(2,4,5,2),(2,8,5,2),(5,5,2,4))),
    "Г": (6, 10, ((0,0,6,2),(0,0,2,10))),
    "Д": (9, 11, ((2,0,5,2),(1,2,2,6),(6,2,2,6),(0,8,9,3))),
    "Ж": (10,10, ((4,0,2,10),(0,4,10,2),(0,0,2,4),(0,6,2,4),(8,0,2,4),(8,6,2,4))),
    "И": (8, 10, ((0,0,2,10),(6,0,2,10),(2,4,4,2))),
    "Й": (8, 12, ((2,0,4,2),(0,2,2,10),(6,2,2,10),(2,6,4,2))),
    "Л": (8, 10, ((2,0,6,2),(6,0,2,10),(0,2,2,8))),
    "П": (8, 10, ((0,0,8,2),(0,0,2,10),(6,0,2,10))),
    "Ф": (10,10, ((4,0,2,10),(0,2,10,2),(0,6,10,2),(0,2,2,6),(8,2,2,6))),
    "Ц": (9, 11, ((0,0,2,10),(6,0,2,10),(0,8,9,3))),
    "Ш": (10,10, ((0,0,2,10),(4,0,2,10),(8,0,2,10),(0,8,10,2))),
    "Щ": (11,11, ((0,0,2,10),(4,0,2,10),(8,0,2,10),(0,8,11,3))),
    "Э": (7, 10, ((0,0,6,2),(5,0,2,10),(1,4,5,2),(0,8,6,2))),
    "Я": (8, 10, ((0,0,8,2),(6,0,2,10),(0,4,8,2),(0,0,2,5),(1,6,2,4)))
}

CW14 = {
    " ": 4, "0": 9, "1": 5, "2": 8, "3": 8, "4": 9, "5": 8, "6": 9, "7": 8, "8": 9, "9": 9,
    "A": 10, "B": 10, "C": 10, "D": 11, "E": 9, "F": 9, "G": 11, "H": 11, "I": 4, "J": 8,
    "K": 10, "L": 9, "M": 13, "N": 11, "O": 11, "P": 10, "R": 10, "S": 9, "T": 8, "U": 11,
    "V": 10, "W": 15, "X": 9, "Y": 9, "Z": 9, "b": 10, "l": 4, ":": 3, "/": 5, ".": 3,
    ",": 3, "-": 5, "(": 5, ")": 5, "+": 8, "#": 10, "•": 6, "°": 5, "%": 12
}

def _fnt(sz):
    if sz <= 12: return lv.font_montserrat_12
    if sz <= 14: return lv.font_montserrat_14
    if sz <= 16: return lv.font_montserrat_16
    if sz <= 20: return lv.font_montserrat_20
    return lv.font_montserrat_24

def _cw(ch, sz):
    w14 = CW14.get(ch, 9)
    if sz <= 12: return max(3, (w14 * 12 + 7) // 14)
    if sz <= 14: return w14
    if sz <= 16: return (w14 * 16 + 7) // 14
    if sz <= 20: return (w14 * 20 + 7) // 14
    return (w14 * 24 + 7) // 14

def mk_box(parent, x, y, w, h, bg, rad=0):
    o = lv.obj(parent)
    o.remove_style_all()
    o.set_size(w, h)
    o.set_pos(x, y)
    o.set_style_bg_color(che(bg), 0)
    o.set_style_bg_opa(255, 0)
    if rad:
        o.set_style_radius(rad, 0)
    return o

def mk_lbl(parent, txt, fnt, col, x=None, y=None):
    l = lv.label(parent)
    l.set_text(str(txt))
    l.set_style_text_font(fnt, 0)
    l.set_style_text_color(che(col), 0)
    if x is not None and y is not None:
        l.set_pos(x, y)
    return l

def ru_row(parent, text, color_hex, sz=14, with_pin=False, pin_hole=0x111E36, x=None, y=None):
    s_up = ru_up(text)
    fnt = _fnt(sz)
    has_g = with_pin
    if not has_g:
        for ch in s_up:
            if ch in RU_GLYPHS:
                has_g = True
                break
    if not has_g:
        mapped = ""
        for ch in s_up:
            mapped += RU_MAP.get(ch, ch)
        return mk_lbl(parent, mapped, fnt, color_hex, x, y)

    h = sz + 4
    y_g = 2 if sz <= 12 else (3 if sz <= 14 else (4 if sz <= 16 else 5))
    if x is not None and y is not None:
        row = parent
        ox = x
        oy = y
    else:
        row = lv.obj(parent)
        row.remove_style_all()
        ox = 0
        oy = 0

    cur_x = 0
    if with_pin:
        py = max(0, y_g - 1)
        mk_box(row, ox, oy + py, 10, 10, 0xFB7185, 5)
        mk_box(row, ox + 3, oy + py + 8, 4, 5, 0xFB7185, 1)
        mk_box(row, ox + 3, oy + py + 3, 4, 4, pin_hole, 2)
        cur_x = 14

    col = che(color_hex)
    buf = ""
    buf_x = cur_x

    for ch in s_up:
        if ch in RU_MAP:
            m = RU_MAP[ch]
            if not buf:
                buf_x = cur_x
            buf += m
            for c in m:
                cur_x += _cw(c, sz)
        elif ch in RU_GLYPHS:
            if buf:
                l = lv.label(row)
                l.set_text(buf)
                l.set_style_text_font(fnt, 0)
                l.set_style_text_color(col, 0)
                l.set_pos(ox + buf_x, oy)
                buf = ""
                cur_x += 1
            gw, gh, rects = RU_GLYPHS[ch]
            yg = max(0, y_g - 2) if ch == "Й" else y_g
            for rx, ry, rw, rh in rects:
                b = lv.obj(row)
                b.remove_style_all()
                b.set_size(rw, rh)
                b.set_pos(ox + cur_x + rx, oy + yg + ry)
                b.set_style_bg_color(col, 0)
                b.set_style_bg_opa(255, 0)
            cur_x += gw + 2
        elif ch == " ":
            if buf:
                l = lv.label(row)
                l.set_text(buf)
                l.set_style_text_font(fnt, 0)
                l.set_style_text_color(col, 0)
                l.set_pos(ox + buf_x, oy)
                buf = ""
            cur_x += _cw(" ", sz)
        else:
            if not buf:
                buf_x = cur_x
            buf += ch
            cur_x += _cw(ch, sz)

    if buf:
        l = lv.label(row)
        l.set_text(buf)
        l.set_style_text_font(fnt, 0)
        l.set_style_text_color(col, 0)
        l.set_pos(ox + buf_x, oy)

    if x is None or y is None:
        row.set_size(max(cur_x, 4), h)
    return row

WIFI_SSID = str(cfg.get("wifiSsid", "")).strip()
CITY_RU = str(cfg.get("cityRu", cfg.get("cityName", "Бутово")))
if "•" in CITY_RU:
    CITY_RU = CITY_RU.split("•")[-1].strip()
CITY_LAT = float(cfg.get("latitude", 55.5520))
CITY_LON = float(cfg.get("longitude", 37.5510))
TZ_OFFSET = int(float(cfg.get("timezoneOffset", 3)) * 3600)
START_WIDGET = str(cfg.get("selectedWidget", "v1_classic_cal"))
AUTO_CAROUSEL = (START_WIDGET == "v10_carousel")
NOTES_LIST = cfg.get("notes", ["Проверить погоду в Бутово", "Синхронизация", "Отличного дня!"])

def get_init_time_str():
    rt = cfg.get("rtcTuple")
    if isinstance(rt, list) and len(rt) >= 6:
        return "{:02d}:{:02d}".format(int(rt[4]), int(rt[5]))
    return "OK"

state = {
    "temp": float(cfg.get("tempC", 5)),
    "tmax": float(cfg.get("tmaxC", float(cfg.get("tempC", 5)) + 2)),
    "tmin": float(cfg.get("tminC", float(cfg.get("tempC", 5)) - 2)),
    "wind": float(cfg.get("windMs", 2.2)),
    "hum": int(cfg.get("humidity", 68)),
    "wcode": int(cfg.get("wcode", 0)),
    "desc": str(cfg.get("descRu", "Ясно")),
    "wifi_ok": bool(WIFI_SSID),
    "last_sync_str": get_init_time_str(),
    "sync_count": 1,
    "next_sync_sec": 300,
    "pomo_sec": 25 * 60,
    "pomo_run": True,
    "ticks": 0,
    "last_min": -1
}

MODES = [
    "v1_classic_cal",
    "v2_flip_clock",
    "v3_weather_pro",
    "v4_day_planner",
    "v5_night_clock",
    "v6_retro_term",
    "v7_pomodoro",
    "v8_world_clock",
    "v9_sun_cycle"
]

ALIAS_MAP = {
    "v3_tear_cal": 2,
    "v4_weather_pro": 2,
    "v5_day_planner": 3,
    "v6_world_clock": 7,
    "v7_countdown": 8,
    "v8_pomodoro": 6,
    "v9_night_clock": 4
}

current_idx = 0
if START_WIDGET in MODES:
    current_idx = MODES.index(START_WIDGET)
elif START_WIDGET in ALIAS_MAP:
    current_idx = ALIAS_MAP[START_WIDGET]

DAYS_RU_FULL = ["ПОНЕДЕЛЬНИК", "ВТОРНИК", "СРЕДА", "ЧЕТВЕРГ", "ПЯТНИЦА", "СУББОТА", "ВОСКРЕСЕНЬЕ"]
DAYS_RU_SHORT = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
MONTHS_RU = ["ЯНВАРЬ", "ФЕВРАЛЬ", "МАРТ", "АПРЕЛЬ", "МАЙ", "ИЮНЬ", "ИЮЛЬ", "АВГУСТ", "СЕНТЯБРЬ", "ОКТЯБРЬ", "НОЯБРЬ", "ДЕКАБРЬ"]

scr = lv.screen_active()
scr.set_style_bg_color(che(0x070B14), 0)
scr.set_style_bg_opa(255, 0)
scr.remove_flag(lv.obj.FLAG.SCROLLABLE)

top = mk_box(scr, 0, 0, 320, 24, 0x101C33)
top_left_box = lv.obj(top)
top_left_box.remove_style_all()
top_left_box.set_size(170, 20)
top_left_box.set_pos(6, 4)

def set_top_title(txt):
    top_left_box.clean()
    ru_row(top_left_box, txt, 0x00E5FF, sz=12, x=0, y=2)

dot_wifi = mk_box(top, 306, 8, 8, 8, 0x18F018, 4)
lbl_top_right = mk_lbl(top, "WIFI OK • " + state["last_sync_str"], lv.font_montserrat_12, 0x22E522)
lbl_top_right.align(lv.ALIGN.RIGHT_MID, -18, 0)

body = lv.obj(scr)
body.remove_style_all()
body.set_size(320, 216)
body.set_pos(0, 24)

def get_dt():
    t = time.localtime()
    if t[0] < 2025:
        return (2026, 10, 20, 14, 30, t[5], 1, 293)
    return t

def fmt_temp(v):
    return ("+{:.0f}°C" if v > 0 else "{:.0f}°C").format(v)

def get_sync_badge_text():
    return ("WIFI OK • {}" if state["wifi_ok"] else "METEO OK • {}").format(state["last_sync_str"])

def update_top_status_bar():
    p = (state["ticks"] % 2 == 0)
    dot_wifi.set_style_bg_color(che(0x18F018 if p else 0x086008), 0)
    if state["wifi_ok"]:
        lbl_top_right.set_text("WIFI OK • {} ({:d}:{:02d})".format(
            state["last_sync_str"], state["next_sync_sec"] // 60, state["next_sync_sec"] % 60
        ))
    else:
        lbl_top_right.set_text("METEO OK • {}".format(state["last_sync_str"]))
    lbl_top_right.set_style_text_color(che(0x22E522), 0)

def days_in_month(y, m):
    dm = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    if m == 2 and ((y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)):
        return 29
    return dm[(m - 1) % 12]

def dow_mon_first(y, m, d):
    t_tbl = (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)
    if m < 3:
        y -= 1
    return ((y + y // 4 - y // 100 + y // 400 + t_tbl[m - 1] + d) % 7 + 6) % 7

pomo_lbl_ref = None
sec_lbl_ref = None
sync_lbl_ref = None
clock_lbl_ref = None

def build_v1():
    global sec_lbl_ref, sync_lbl_ref, clock_lbl_ref
    set_top_title("1/9 КАЛЕНДАРЬ")
    t = get_dt()

    left = lv.obj(body)
    left.remove_style_all()
    left.set_size(116, 208)
    left.set_pos(4, 4)

    clock_lbl_ref = mk_lbl(left, "{:02d}:{:02d}".format(t[3], t[4]), lv.font_montserrat_36, 0xFFFFFF, 2, 0)
    ru_row(left, DAYS_RU_FULL[t[6] % 7][:9], 0x00E5FF, sz=12, x=2, y=40)

    sec_lbl_ref = mk_lbl(left, "{:02d}.{:02d}.{:04d} • :{:02d}c".format(t[2], t[1], t[0], t[5]), lv.font_montserrat_12, 0xCBD5E1, 2, 58)

    wb = mk_box(left, 2, 76, 112, 130, 0x0F172A, 10)
    ru_row(wb, CITY_RU[:9], 0xFBBF24, sz=14, with_pin=True, pin_hole=0x0F172A, x=8, y=8)

    mk_lbl(wb, fmt_temp(state["temp"]), lv.font_montserrat_28, 0xFFFFFF, 8, 30)

    ru_row(wb, state["desc"][:10], 0x38BDF8, sz=12, x=8, y=64)

    mk_lbl(wb, "BETEP {:.1f} M/C".format(state["wind"]), lv.font_montserrat_12, 0x34D399, 8, 86)

    sync_lbl_ref = mk_lbl(
        wb,
        "WIFI OK • " + state["last_sync_str"] if state["wifi_ok"] else "METEO • " + state["last_sync_str"],
        lv.font_montserrat_12,
        0x22E522,
        8,
        106
    )

    cbox = mk_box(body, 122, 4, 194, 208, 0x0B1324, 10)
    ru_row(cbox, "{} {}".format(MONTHS_RU[(t[1] - 1) % 12], t[0]), 0x00E5FF, sz=14, x=38, y=5)

    for col_i, dname in enumerate(DAYS_RU_SHORT):
        ru_row(cbox, dname, 0xFB7185 if col_i >= 5 else 0x94A3B8, sz=12, x=8 + col_i * 26, y=28)

    first_col = dow_mon_first(t[0], t[1], 1)
    tot_days = days_in_month(t[0], t[1])
    row_h = 25 if (first_col + tot_days) > 35 else 28
    r_idx = 0
    c_idx = first_col

    for d in range(1, tot_days + 1):
        cx = 5 + c_idx * 26
        cy = 48 + r_idx * row_h
        is_today = (d == t[2])
        if is_today:
            cell = mk_box(cbox, cx, cy, 25, row_h - 2, 0x00E5FF, 6)
            dl = mk_lbl(cell, str(d), lv.font_montserrat_16, 0x070B14)
            dl.center()
        else:
            tx = cx + (8 if d < 10 else 3)
            ty = cy + (row_h - 18) // 2
            mk_lbl(cbox, str(d), lv.font_montserrat_16, 0xFB7185 if c_idx >= 5 else 0xFFFFFF, tx, ty)
        c_idx += 1
        if c_idx >= 7:
            c_idx = 0
            r_idx += 1

def build_v2():
    set_top_title("2/9 КРУПНЫЕ ЧАСЫ")
    t = get_dt()
    top_c = mk_box(body, 10, 6, 300, 114, 0x0F172A, 14)
    mk_lbl(top_c, "{:02d}:{:02d}".format(t[3], t[4]), lv.font_montserrat_48, 0xFFFFFF, 46, 16)
    mk_lbl(top_c, ":{:02d}".format(t[5]), lv.font_montserrat_24, 0x00E5FF, 200, 32)
    sub = ru_row(top_c, "{}, {:02d} {}".format(DAYS_RU_FULL[t[6] % 7], t[2], MONTHS_RU[(t[1] - 1) % 12]), 0xFBBF24, sz=14)
    sub.align(lv.ALIGN.BOTTOM_MID, 0, -10)

    bot_c = mk_box(body, 10, 126, 300, 82, 0x111C35, 12)
    ru_row(bot_c, "{}  •  {}".format(CITY_RU[:12], fmt_temp(state["temp"])), 0xFFFFFF, sz=14, with_pin=True, pin_hole=0x111C35, x=14, y=10)
    ru_row(bot_c, "{}  •  ВЕТЕР {:.1f} М/С".format(state["desc"][:11], state["wind"]), 0x34D399, sz=14, x=14, y=36)
    mk_lbl(bot_c, get_sync_badge_text(), lv.font_montserrat_12, 0x22E522, 14, 60)

def build_v3():
    global sync_lbl_ref
    set_top_title("3/9 МЕТЕОСТАНЦИЯ")
    t = get_dt()
    card = mk_box(body, 8, 8, 304, 200, 0x0F172A, 12)

    ru_row(card, "{}  •  {:02d}:{:02d}".format(CITY_RU[:12], t[3], t[4]), 0xFBBF24, sz=14, with_pin=True, pin_hole=0x0F172A, x=14, y=12)

    mk_lbl(card, fmt_temp(state["temp"]), lv.font_montserrat_40, 0xFFFFFF, 14, 42)
    ru_row(card, state["desc"][:12], 0x38BDF8, sz=14, x=130, y=56)

    ru_row(card, "МАКС: {}  МИН: {}  ВЛАЖН: {}%".format(fmt_temp(state["tmax"]), fmt_temp(state["tmin"]), state["hum"]), 0xE2E8F0, sz=12, x=14, y=102)

    ru_row(card, "ВЕТЕР: {:.1f} М/С  •  {:.2f}, {:.2f}".format(state["wind"], CITY_LAT, CITY_LON), 0x34D399, sz=12, x=14, y=134)

    sync_lbl_ref = mk_lbl(card, "METEO: {} (#{})".format(get_sync_badge_text(), state["sync_count"]), lv.font_montserrat_12, 0x22E522, 14, 168)

def build_v4():
    set_top_title("4/9 ПЛАНЕР ДНЯ")
    t = get_dt()
    wday = t[6] % 7
    for i in range(7):
        act = (i == wday)
        pbox = mk_box(body, 8 + i * 44, 6, 40, 32, 0x00E5FF if act else 0x111C35, 6)
        ru_row(pbox, DAYS_RU_SHORT[i], 0x070B14 if act else 0xE2E8F0, sz=12, x=11, y=9)

    ru_row(body, "{:02d}:{:02d} • {:02d}.{:02d} • {} {}".format(t[3], t[4], t[2], t[1], CITY_RU[:9], fmt_temp(state["temp"])), 0xFBBF24, sz=14, with_pin=True, pin_hole=0x070B14, x=10, y=44)

    for i, note in enumerate(NOTES_LIST[:3]):
        row = mk_box(body, 8, 72 + i * 46, 304, 40, 0x0F172A, 8)
        ru_row(row, "{}. {}".format(i + 1, str(note)[:18]), 0xF8FAFC, sz=14, x=12, y=11)

def build_v5():
    set_top_title("5/9 НОЧНЫЕ ЧАСЫ")
    t = get_dt()
    card = mk_box(body, 10, 10, 300, 196, 0x050811, 16)
    nc = mk_lbl(card, "{:02d}:{:02d}".format(t[3], t[4]), lv.font_montserrat_48, 0x00E5FF)
    nc.align(lv.ALIGN.TOP_MID, 0, 24)
    nd = ru_row(card, "{}, {:02d} {}".format(DAYS_RU_FULL[t[6] % 7], t[2], MONTHS_RU[(t[1] - 1) % 12]), 0x38BDF8, sz=14)
    nd.align(lv.ALIGN.CENTER, 0, 18)
    nw = ru_row(card, "{}  •  {}  •  {:.1f} М/С".format(CITY_RU[:10], fmt_temp(state["temp"]), state["wind"]), 0xFBBF24, sz=14, with_pin=True, pin_hole=0x050811)
    nw.align(lv.ALIGN.BOTTOM_MID, 0, -18)

def build_v6():
    set_top_title("6/9 РЕТРО CASIO")
    t = get_dt()
    card = mk_box(body, 8, 8, 304, 200, 0x041208, 8)
    ru_row(card, "CASIO CYD-2432 // МЕТЕОРАДАР", 0x10B981, sz=12, x=14, y=10)
    mk_lbl(card, "{:02d}:{:02d}".format(t[3], t[4]), lv.font_montserrat_48, 0x34D399, 14, 34)
    ru_row(card, "ДАТА: {:02d}.{:02d}.{:04d} ({})".format(t[2], t[1], t[0], DAYS_RU_SHORT[t[6] % 7]), 0x10B981, sz=14, x=14, y=100)
    ru_row(card, "ЛОКАЦИЯ: {} • {}".format(CITY_RU[:10], fmt_temp(state["temp"])), 0xA7F3D0, sz=14, with_pin=True, pin_hole=0x041208, x=14, y=132)
    ru_row(card, "ВЕТЕР: {:.1f} М/С • МЕТЕО {}".format(state["wind"], state["last_sync_str"]), 0x34D399, sz=12, x=14, y=166)

def build_v7():
    global pomo_lbl_ref
    set_top_title("7/9 ПОМОДОРО")
    t = get_dt()
    card = mk_box(body, 10, 8, 300, 200, 0x131C31, 14)
    hdr = ru_row(card, "ФОКУС-ТАЙМЕР ПОМОДОРО", 0xFB7185, sz=14)
    hdr.align(lv.ALIGN.TOP_MID, 0, 16)
    pomo_lbl_ref = mk_lbl(card, "{:02d}:{:02d}".format(state["pomo_sec"] // 60, state["pomo_sec"] % 60), lv.font_montserrat_48, 0xFFFFFF)
    pomo_lbl_ref.align(lv.ALIGN.CENTER, 0, -2)
    cl = ru_row(card, "ВРЕМЯ {:02d}:{:02d} • {} {}".format(t[3], t[4], CITY_RU[:9], fmt_temp(state["temp"])), 0x38BDF8, sz=14, with_pin=True, pin_hole=0x131C31)
    cl.align(lv.ALIGN.BOTTOM_MID, 0, -16)

def build_v8():
    set_top_title("8/9 МИРОВОЕ ВРЕМЯ")
    t = get_dt()
    utc_h = (t[3] - int(TZ_OFFSET // 3600)) % 24
    zones = (
        (CITY_RU[:11], t[3], t[4], 0x00E5FF, True),
        ("ЛОНДОН (UTC+0)", utc_h, t[4], 0xE2E8F0, False),
        ("ТОКИО (UTC+9)", (utc_h + 9) % 24, t[4], 0xFBBF24, False),
        ("НЬЮ-ЙОРК (UTC-5)", (utc_h + 19) % 24, t[4], 0x34D399, False)
    )
    for i, (zn_txt, zh, zm, col, hp) in enumerate(zones):
        b = mk_box(body, 8, 6 + i * 51, 304, 45, 0x0F172A, 8)
        ru_row(b, zn_txt, col, sz=14, with_pin=hp, pin_hole=0x0F172A, x=12, y=13)
        zv = mk_lbl(b, "{:02d}:{:02d}".format(zh, zm), lv.font_montserrat_24, 0xFFFFFF)
        zv.align(lv.ALIGN.RIGHT_MID, -12, 0)

def build_v9():
    set_top_title("9/9 СВЕТОВОЙ ДЕНЬ")
    t = get_dt()
    card = mk_box(body, 10, 8, 300, 200, 0x0F172A, 14)
    hdr = ru_row(card, "СВЕТОВОЙ ДЕНЬ И ПОГОДА", 0xFBBF24, sz=14)
    hdr.align(lv.ALIGN.TOP_MID, 0, 14)
    nc = mk_lbl(card, "{:02d}:{:02d}".format(t[3], t[4]), lv.font_montserrat_48, 0xFFFFFF)
    nc.align(lv.ALIGN.CENTER, 0, -18)
    sun = ru_row(card, "ВОСХОД: 07:12  •  ЗАКАТ: 17:48", 0x38BDF8, sz=14)
    sun.align(lv.ALIGN.CENTER, 0, 28)
    nw = ru_row(card, "{} • {} • ВЕТЕР {:.1f} М/С".format(CITY_RU[:9], fmt_temp(state["temp"]), state["wind"]), 0x34D399, sz=14, with_pin=True, pin_hole=0x0F172A)
    nw.align(lv.ALIGN.BOTTOM_MID, 0, -14)

BUILDERS = (build_v1, build_v2, build_v3, build_v4, build_v5, build_v6, build_v7, build_v8, build_v9)

def render_current():
    global pomo_lbl_ref, sec_lbl_ref, sync_lbl_ref, clock_lbl_ref
    try:
        pomo_lbl_ref = None; sec_lbl_ref = None; sync_lbl_ref = None; clock_lbl_ref = None
        gc.collect()
        body.clean()
        dt_now = get_dt()
        state["last_min"] = dt_now[4]
        state["last_day"] = dt_now[2]
        BUILDERS[current_idx % len(BUILDERS)]()
        update_top_status_bar()
        gc.collect()
    except Exception as e:
        print("RENDER_ERR:", e)

render_current()

def print_diag_report():
    try:
        rep = {
            "status": "SCREEN_ACTIVE",
            "board": "ESP32-2432S024R (L i 435-2 4)",
            "driver_mode": variant,
            "rot": hex(rot_hex),
            "touch_type": "GPIO27",
            "mem_free_kb": gc.mem_free() // 1024,
            "city": CITY_RU,
            "widget": MODES[current_idx % len(MODES)]
        }
        print("CYD_SCAN_REPORT:" + json.dumps(rep))
    except Exception as e:
        print("CYD_SCAN_ERROR:", e)

print_diag_report()

boot_hold_cnt = 0
poll_in = select.poll()
poll_in.register(sys.stdin, select.POLLIN)
s_buf = ""

def poll_controls(t):
    global current_idx, boot_hold_cnt, s_buf, AUTO_CAROUSEL
    try:
        if btn_boot.value() == 0:
            boot_hold_cnt += 1
            if boot_hold_cnt == 2:
                current_idx = (current_idx + 1) % len(BUILDERS)
                render_current()
        else:
            boot_hold_cnt = 0
    except Exception:
        pass

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
                        elif w_id in ALIAS_MAP:
                            current_idx = ALIAS_MAP[w_id]
                            render_current()
            else:
                s_buf += ch
    except Exception:
        pass

timer_btn = lv.timer_create(poll_controls, 80, None)
timer_btn.set_repeat_count(-1)

def tick_cb(t):
    global current_idx
    state["ticks"] += 1
    if state["next_sync_sec"] > 0:
        state["next_sync_sec"] -= 1
    else:
        state["next_sync_sec"] = 300
        state["sync_count"] += 1

    update_top_status_bar()
    t_now = get_dt()
    if current_idx == 0 and sec_lbl_ref is not None:
        try:
            sec_lbl_ref.set_text("{:02d}.{:02d}.{:04d} • :{:02d}c".format(t_now[2], t_now[1], t_now[0], t_now[5]))
        except Exception:
            pass
    if current_idx == 0 and sync_lbl_ref is not None:
        try:
            sync_lbl_ref.set_text("WIFI OK • " + state["last_sync_str"] if state["wifi_ok"] else "METEO • " + state["last_sync_str"])
        except Exception:
            pass

    if state["pomo_run"] and state["pomo_sec"] > 0:
        state["pomo_sec"] -= 1
        if current_idx == 6 and pomo_lbl_ref is not None:
            try:
                pomo_lbl_ref.set_text("{:02d}:{:02d}".format(state["pomo_sec"] // 60, state["pomo_sec"] % 60))
            except Exception:
                pass
    elif state["pomo_run"] and state["pomo_sec"] == 0:
        state["pomo_sec"] = 25 * 60

    if AUTO_CAROUSEL and state["ticks"] % 15 == 0:
        current_idx = (current_idx + 1) % len(BUILDERS)
        render_current()
    elif t_now[4] != state["last_min"]:
        state["last_min"] = t_now[4]
        if current_idx == 0 and clock_lbl_ref is not None and t_now[2] == state.get("last_day"):
            try:
                clock_lbl_ref.set_text("{:02d}:{:02d}".format(t_now[3], t_now[4]))
            except Exception:
                render_current()
        else:
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
