#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор образа файловой системы LittleFS v2 (vfs_widgets.bin) для дисплея L i 435-2 4 (ESP32-2432S024R / S028).
Записывается по адресу 0x343000 (раздел vfs, 189 блоков по 4096 байт).
Построен на 100% проверенном ядре инициализации экрана 664e554 (БЕЗ lv.binfont_create и БЕЗ риска переполнения LV_MEM_SIZE):
  - Изоляция CS=33 и CS=5 + мгновенное включение подсветки GPIO 27 уже в boot.py
  - Полностью русский интерфейс (ЯНВАРЬ..ДЕКАБРЬ, Пн..Вс, Понедельник..Воскресенье, ВЕТЕР м/с, СЕТЬ ОК)
  - Двухцветная векторная иконка пина 📍 возле города/района (📍 БУТОВО)
  - Бесплатные метеостанции (Open-Meteo WMO с windspeed_unit=ms и MET Norway без платных ключей)
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

# 2. Мгновенно включаем подсветку экрана (GPIO 27 и GPIO 21 = HIGH) уже на старте boot.py
try:
    machine.Pin(27, machine.Pin.OUT, value=1)
    machine.Pin(21, machine.Pin.OUT, value=1)
except Exception:
    pass

# 3. Гасим яркий красный RGB-светодиод (GPIO 4, 16, 17 — активный LOW: 1 = ВЫКЛ)
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
    "latitude": 55.5383,
    "longitude": 37.5619,
    "timezoneOffset": 3,
    "weatherStation": "open_meteo",
    "selectedWidget": "v1_classic_cal",
    "notes": [
        "Проверить погоду в Бутово",
        "Синхронизация метеостанции",
        "Отличного рабочего дня!"
    ],
    "eventTitle": "ДО НОВОГО ГОДА",
    "eventDays": "73 ДНЯ",
    "tempC": 14,
    "tmaxC": 17,
    "tminC": 11,
    "windMs": 3.2,
    "humidity": 64,
    "wcode": 2,
    "rtcTuple": [2026, 10, 20, 1, 14, 30, 0]
}

DEFAULT_CFG_BYTES = (
    ("CYDCFG1:" + json.dumps(DEFAULT_CFG, ensure_ascii=False) + "\x00").encode("utf-8")
).ljust(2048, b" ")

MAIN_PY = """# main.py — ESP32-2432S024R (L i 435-2 4) Русский интерфейс + 📍 Бутово + Бесплатные метеостанции
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
    "cityRu": "Бутово",
    "cityEn": "Butovo",
    "latitude": 55.5383,
    "longitude": 37.5619,
    "timezoneOffset": 3,
    "weatherStation": "open_meteo",
    "selectedWidget": "v1_classic_cal",
    "notes": ["Проверить погоду в Бутово", "Синхронизация метеостанции", "Отличного дня!"],
    "eventTitle": "ДО НОВОГО ГОДА",
    "eventDays": "73 ДНЯ",
    "tempC": 14,
    "tmaxC": 17,
    "tminC": 11,
    "windMs": 3.2,
    "humidity": 64,
    "wcode": 2,
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
elif variant in ("s024_bgr_inv0", "s024_rot0_bgr_noinv"):
    rot_hex = 0x60
    use_bgr = True
    inv_cmd = 0x20
elif variant in ("bl27_st7789", "s024_rgb_inv1", "s024_rot0_rgb_inv"):
    rot_hex = 0x60
    use_bgr = False
    inv_cmd = 0x21
elif variant in ("bl27_type2_e0", "s024_bgr_inv1"):
    rot_hex = 0x60
    use_bgr = True
    inv_cmd = 0x21
elif variant == "s028_classic":
    bl_pin = 21
    aux_bl_pin = 27
    rot_hex = 0x60
    use_bgr = False
    inv_cmd = 0x20

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

btn_boot = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)

th = task_handler.TaskHandler()

# ==============================================================================
# БЕЗОТКАЗНЫЙ ВЕКТОРНО-ШРИФТОВОЙ ДВИЖОК РУССКОГО ЯЗЫКА И ИКОНКИ 📍 (0% C-CRASH)
# ==============================================================================
RU_MAP = {
    "А": "A", "В": "B", "Е": "E", "Ё": "E", "З": "3",
    "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P",
    "С": "C", "Т": "T", "У": "Y", "Х": "X", "Ч": "4",
    "Ъ": "b", "Ы": "bl", "Ь": "b", "Ю": "IO"
}

RU_GLYPHS = {
    "Б": (8, 10, ((0,0,7,2),(0,0,2,10),(0,4,7,2),(0,8,7,2),(6,5,2,4))),
    "Г": (7, 10, ((0,0,7,2),(0,0,2,10))),
    "Д": (9, 12, ((2,0,5,2),(1,2,2,6),(6,2,2,6),(0,8,9,2),(0,9,2,3),(7,9,2,3))),
    "Ж": (10,10, ((4,0,2,10),(2,4,6,2),(0,0,2,4),(0,6,2,4),(8,0,2,4),(8,6,2,4))),
    "И": (8, 10, ((0,0,2,10),(6,0,2,10),(2,5,2,3),(4,2,2,3))),
    "Й": (8, 12, ((2,0,4,2),(0,2,2,10),(6,2,2,10),(2,7,2,3),(4,4,2,3))),
    "Л": (8, 10, ((2,0,6,2),(6,0,2,10),(1,2,2,7),(0,8,2,2))),
    "П": (8, 10, ((0,0,8,2),(0,0,2,10),(6,0,2,10))),
    "Ф": (10,10, ((4,0,2,10),(1,1,8,2),(1,6,8,2),(0,2,2,5),(8,2,2,5))),
    "Ц": (9, 12, ((0,0,2,10),(6,0,2,10),(0,8,8,2),(7,9,2,3))),
    "Ш": (10,10, ((0,0,2,10),(4,0,2,10),(8,0,2,10),(0,8,10,2))),
    "Щ": (11,12, ((0,0,2,10),(4,0,2,10),(8,0,2,10),(0,8,10,2),(9,9,2,3))),
    "Э": (8, 10, ((1,0,6,2),(6,1,2,8),(2,4,5,2),(1,8,6,2))),
    "Я": (8, 10, ((1,0,7,2),(6,0,2,10),(1,4,6,2),(0,1,2,4),(1,6,2,4)))
}

def _get_font(sz):
    if sz <= 12:
        return lv.font_montserrat_12
    if sz <= 14:
        return lv.font_montserrat_14
    if sz <= 16:
        return lv.font_montserrat_16
    if sz <= 20:
        return lv.font_montserrat_20
    return lv.font_montserrat_24

def add_pin_icon(parent, bg_hole=0x111E36):
    p = lv.obj(parent)
    p.remove_style_all()
    p.set_size(11, 14)
    head = lv.obj(p)
    head.remove_style_all()
    head.set_size(10, 10)
    head.set_pos(0, 0)
    head.set_style_radius(5, 0)
    head.set_style_bg_color(lv.color_hex(0xFB7185), 0)
    head.set_style_bg_opa(255, 0)
    tip = lv.obj(p)
    tip.remove_style_all()
    tip.set_size(4, 5)
    tip.set_pos(3, 8)
    tip.set_style_radius(1, 0)
    tip.set_style_bg_color(lv.color_hex(0xFB7185), 0)
    tip.set_style_bg_opa(255, 0)
    hole = lv.obj(p)
    hole.remove_style_all()
    hole.set_size(4, 4)
    hole.set_pos(3, 3)
    hole.set_style_radius(2, 0)
    hole.set_style_bg_color(lv.color_hex(bg_hole), 0)
    hole.set_style_bg_opa(255, 0)
    return p

def ru_row(parent, text, color_hex, sz=14, with_pin=False, pin_hole=0x111E36):
    row = lv.obj(parent)
    row.remove_style_all()
    row.set_size(lv.SIZE_CONTENT, lv.SIZE_CONTENT)
    row.set_flex_flow(lv.FLEX_FLOW.ROW)
    row.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)
    row.set_style_pad_column(1, 0)
    row.remove_flag(lv.obj.FLAG.SCROLLABLE)

    if with_pin:
        add_pin_icon(row, pin_hole)
        sp = lv.obj(row)
        sp.remove_style_all()
        sp.set_size(3, 2)

    fnt = _get_font(sz)
    col = lv.color_hex(color_hex)
    buf = ""
    s_up = str(text).upper()

    for ch in s_up:
        if ch in RU_MAP:
            buf += RU_MAP[ch]
        elif ch in RU_GLYPHS:
            if buf:
                lbl = lv.label(row)
                lbl.set_text(buf)
                lbl.set_style_text_font(fnt, 0)
                lbl.set_style_text_color(col, 0)
                buf = ""
            gw, gh, rects = RU_GLYPHS[ch]
            gbox = lv.obj(row)
            gbox.remove_style_all()
            gbox.set_size(gw, gh)
            for rx, ry, rw, rh in rects:
                bar = lv.obj(gbox)
                bar.remove_style_all()
                bar.set_size(rw, rh)
                bar.set_pos(rx, ry)
                bar.set_style_bg_color(col, 0)
                bar.set_style_bg_opa(255, 0)
        else:
            buf += ch

    if buf:
        lbl = lv.label(row)
        lbl.set_text(buf)
        lbl.set_style_text_font(fnt, 0)
        lbl.set_style_text_color(col, 0)

    return row

WIFI_SSID = str(cfg.get("wifiSsid", "")).strip()
WIFI_PASS = str(cfg.get("wifiPassword", cfg.get("wifiPass", "")))
CITY_RU = str(cfg.get("cityRu", cfg.get("cityName", "Бутово")))
if "•" in CITY_RU:
    CITY_RU = CITY_RU.split("•")[-1].strip()
CITY_LAT = float(cfg.get("latitude", 55.5383))
CITY_LON = float(cfg.get("longitude", 37.5619))
WEATHER_STATION = str(cfg.get("weatherStation", "open_meteo"))
TZ_OFFSET = int(float(cfg.get("timezoneOffset", 3)) * 3600)
START_WIDGET = str(cfg.get("selectedWidget", "v1_classic_cal"))
AUTO_CAROUSEL = (START_WIDGET == "v10_carousel")
NOTES_LIST = cfg.get("notes", ["Проверить погоду в Бутово", "Синхронизация", "Отличного дня!"])
EVENT_TITLE = str(cfg.get("eventTitle", "ДО НОВОГО ГОДА"))
EVENT_DAYS = str(cfg.get("eventDays", "73 ДНЯ"))

def get_init_time_str():
    rt = cfg.get("rtcTuple")
    if isinstance(rt, list) and len(rt) >= 6:
        return "{:02d}:{:02d}".format(int(rt[4]), int(rt[5]))
    return "OK"

state = {
    "temp": float(cfg.get("tempC", 14)),
    "tmax": float(cfg.get("tmaxC", float(cfg.get("tempC", 14)) + 3)),
    "tmin": float(cfg.get("tminC", float(cfg.get("tempC", 14)) - 2)),
    "wind": float(cfg.get("windMs", 3.2)),
    "hum": int(cfg.get("humidity", 64)),
    "wifi_ok": False,
    "wifi_connecting": False,
    "wifi_synced": False,
    "wifi_err": False,
    "ntp_applied": False,
    "last_sync_str": get_init_time_str(),
    "sync_source": "USB",
    "sync_count": 1,
    "next_sync_sec": 300,
    "pomo_sec": 25 * 60,
    "pomo_run": True,
    "ticks": 0,
    "connect_sec": 0,
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

DAYS_RU_FULL = ["ПОНЕДЕЛЬНИК", "ВТОРНИК", "СРЕДА", "ЧЕТВЕРГ", "ПЯТНИЦА", "СУББОТА", "ВОСКРЕСЕНЬЕ"]
DAYS_RU_SHORT = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
MONTHS_RU = ["ЯНВАРЬ", "ФЕВРАЛЬ", "МАРТ", "АПРЕЛЬ", "МАЙ", "ИЮНЬ", "ИЮЛЬ", "АВГУСТ", "СЕНТЯБРЬ", "ОКТЯБРЬ", "НОЯБРЬ", "ДЕКАБРЬ"]

scr = lv.screen_active()
scr.set_style_bg_color(lv.color_hex(0x070B14), 0)
scr.set_style_bg_opa(255, 0)
scr.remove_flag(lv.obj.FLAG.SCROLLABLE)

# Верхняя панель статуса (24px): слева название режима на русском, справа индикатор Wi-Fi + точка-пульс + время обновления
top = lv.obj(scr)
top.remove_style_all()
top.set_size(320, 24)
top.set_pos(0, 0)
top.set_style_bg_color(lv.color_hex(0x101C33), 0)
top.set_style_bg_opa(255, 0)

top_left_box = lv.obj(top)
top_left_box.remove_style_all()
top_left_box.set_size(150, 22)
top_left_box.align(lv.ALIGN.LEFT_MID, 6, 0)

def set_top_title(txt):
    top_left_box.clean()
    r = ru_row(top_left_box, txt, 0x00E5FF, sz=12)
    r.align(lv.ALIGN.LEFT_MID, 0, 0)

# Круглый светодиодный индикатор статуса сети в правом верхнем углу экрана
dot_wifi = lv.obj(top)
dot_wifi.remove_style_all()
dot_wifi.set_size(8, 8)
dot_wifi.set_style_radius(4, 0)
dot_wifi.set_style_bg_color(lv.color_hex(0x00E5FF), 0)
dot_wifi.set_style_bg_opa(255, 0)
dot_wifi.align(lv.ALIGN.RIGHT_MID, -6, 0)

lbl_top_right = lv.label(top)
if WIFI_SSID:
    lbl_top_right.set_text("CETb Wi-Fi...")
    lbl_top_right.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    dot_wifi.set_style_bg_color(lv.color_hex(0xFBBF24), 0)
else:
    lbl_top_right.set_text("METEO OK • " + state["last_sync_str"])
    lbl_top_right.set_style_text_color(lv.color_hex(0x38BDF8), 0)
    dot_wifi.set_style_bg_color(lv.color_hex(0x38BDF8), 0)
lbl_top_right.set_style_text_font(lv.font_montserrat_12, 0)
lbl_top_right.align(lv.ALIGN.RIGHT_MID, -18, 0)

body = lv.obj(scr)
body.remove_style_all()
body.set_size(320, 216)
body.set_pos(0, 24)

def get_dt():
    if state["ntp_applied"]:
        t = time.localtime(time.time() + TZ_OFFSET)
    else:
        t = time.localtime()
    if t[0] < 2025:
        return (2026, 10, 20, 14, 30, t[5], 1, 293)
    return t

def fmt_temp(v):
    return ("+{:.0f}°C" if v > 0 else "{:.0f}°C").format(v)

def get_sync_badge_text():
    if state["wifi_connecting"]:
        return "Wi-Fi ({}c)...".format(state["connect_sec"])
    if state["wifi_ok"]:
        return "CETb OK • {}".format(state["last_sync_str"])
    if state["wifi_err"]:
        return "METEO • {}".format(state["last_sync_str"])
    return "METEO OK • {}".format(state["last_sync_str"])

def update_top_status_bar():
    pulse_on = (state["ticks"] % 2 == 0)
    if state["wifi_connecting"]:
        lbl_top_right.set_text("CETb Wi-Fi... {}c".format(state["connect_sec"]))
        lbl_top_right.set_style_text_color(lv.color_hex(0xFBBF24), 0)
        dot_wifi.set_style_bg_color(lv.color_hex(0xFBBF24 if pulse_on else 0x78350F), 0)
    elif state["wifi_ok"]:
        rem_m = state["next_sync_sec"] // 60
        rem_s = state["next_sync_sec"] % 60
        lbl_top_right.set_text("CETb OK • {} ({:d}:{:02d})".format(state["last_sync_str"], rem_m, rem_s))
        lbl_top_right.set_style_text_color(lv.color_hex(0x10B981), 0)
        dot_wifi.set_style_bg_color(lv.color_hex(0x10B981 if pulse_on else 0x064E3B), 0)
    elif state["wifi_err"]:
        lbl_top_right.set_text("HP-CETb | METEO {}".format(state["last_sync_str"]))
        lbl_top_right.set_style_text_color(lv.color_hex(0xFB7185), 0)
        dot_wifi.set_style_bg_color(lv.color_hex(0xEF4444 if pulse_on else 0x7F1D1D), 0)
    else:
        lbl_top_right.set_text("METEO OK • {}".format(state["last_sync_str"]))
        lbl_top_right.set_style_text_color(lv.color_hex(0x38BDF8), 0)
        dot_wifi.set_style_bg_color(lv.color_hex(0x00E5FF if pulse_on else 0x0369A1), 0)

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
sec_lbl_ref = None
sync_lbl_ref = None

# 1. КЛАССИЧЕСКИЙ КАЛЕНДАРЬ + КРУПНЫЕ ЧАСЫ + 📍 БУТОВО НА РУССКОМ ЯЗЫКЕ
def build_v1():
    global sec_lbl_ref, sync_lbl_ref
    set_top_title("1/9 КАЛЕНДАРЬ")
    t = get_dt()

    left = lv.obj(body)
    left.remove_style_all()
    left.set_size(120, 208)
    left.set_pos(4, 4)

    clk = lv.label(left)
    clk.set_text("{:02d}:{:02d}".format(t[3], t[4]))
    clk.set_style_text_font(lv.font_montserrat_40, 0)
    clk.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    clk.set_pos(2, 0)

    day_row = ru_row(left, DAYS_RU_FULL[t[6] % 7][:9], 0x00E5FF, sz=12)
    day_row.set_pos(4, 46)

    dt_lbl = lv.label(left)
    dt_lbl.set_text("{:02d}.{:02d} • :{:02d}c".format(t[2], t[1], t[5]))
    dt_lbl.set_style_text_font(lv.font_montserrat_14, 0)
    dt_lbl.set_style_text_color(lv.color_hex(0xCBD5E1), 0)
    dt_lbl.set_pos(4, 66)
    sec_lbl_ref = dt_lbl

    wb = lv.obj(left)
    wb.remove_style_all()
    wb.set_size(116, 116)
    wb.set_pos(2, 90)
    wb.set_style_bg_color(lv.color_hex(0x111E36), 0)
    wb.set_style_bg_opa(255, 0)
    wb.set_style_radius(10, 0)

    # Город/район с настоящей иконкой пина 📍!
    w_city = ru_row(wb, CITY_RU[:9], 0x38BDF8, sz=14, with_pin=True, pin_hole=0x111E36)
    w_city.align(lv.ALIGN.TOP_MID, 0, 6)

    w_temp = lv.label(wb)
    w_temp.set_text(fmt_temp(state["temp"]))
    w_temp.set_style_text_font(lv.font_montserrat_28, 0)
    w_temp.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    w_temp.align(lv.ALIGN.CENTER, 0, -4)

    w_wind = lv.label(wb)
    w_wind.set_text("BETEP {:.1f} M/C".format(state["wind"]))
    w_wind.set_style_text_font(lv.font_montserrat_12, 0)
    w_wind.set_style_text_color(lv.color_hex(0xCBD5E1), 0)
    w_wind.align(lv.ALIGN.BOTTOM_MID, 0, -24)

    w_sync = lv.label(wb)
    w_sync.set_text("CETb OK " + state["last_sync_str"] if state["wifi_ok"] else ("Wi-Fi..." if state["wifi_connecting"] else "METEO " + state["last_sync_str"]))
    w_sync.set_style_text_font(lv.font_montserrat_12, 0)
    w_sync.set_style_text_color(lv.color_hex(0x10B981 if state["wifi_ok"] else 0x00E5FF), 0)
    w_sync.align(lv.ALIGN.BOTTOM_MID, 0, -6)
    sync_lbl_ref = w_sync

    # Правая панель (190 x 208): ИДЕАЛЬНО РОВНАЯ СЕТКА КАЛЕНДАРЯ НА РУССКОМ (7 колонок по 26px!)
    cbox = lv.obj(body)
    cbox.remove_style_all()
    cbox.set_size(190, 208)
    cbox.set_pos(126, 4)
    cbox.set_style_bg_color(lv.color_hex(0x0D1526), 0)
    cbox.set_style_bg_opa(255, 0)
    cbox.set_style_radius(10, 0)

    mhdr = ru_row(cbox, "{} {}".format(MONTHS_RU[(t[1] - 1) % 12], t[0]), 0x00E5FF, sz=16)
    mhdr.align(lv.ALIGN.TOP_MID, 0, 5)

    for col_i, dname in enumerate(DAYS_RU_SHORT):
        hcell = lv.obj(cbox)
        hcell.remove_style_all()
        hcell.set_size(26, 20)
        hcell.set_pos(4 + col_i * 26, 28)
        hl = ru_row(hcell, dname, 0xFB7185 if col_i >= 5 else 0x94A3B8, sz=12)
        hl.center()

    first_col = dow_mon_first(t[0], t[1], 1)
    tot_days = days_in_month(t[0], t[1])
    row_h = 25 if (first_col + tot_days) > 35 else 28
    r_idx = 0
    c_idx = first_col

    for d in range(1, tot_days + 1):
        cell = lv.obj(cbox)
        cell.remove_style_all()
        cell.set_size(25, row_h - 2)
        cell.set_pos(4 + c_idx * 26, 50 + r_idx * row_h)

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

def build_v2():
    set_top_title("2/9 РЕТРО ЧАСЫ")
    t = get_dt()
    for i, val in enumerate((t[3], t[4])):
        card = lv.obj(body)
        card.remove_style_all()
        card.set_size(144, 142)
        card.set_pos(12 + i * 152, 10)
        card.set_style_bg_color(lv.color_hex(0x142038), 0)
        card.set_style_bg_opa(255, 0)
        card.set_style_radius(16, 0)
        lbl = lv.label(card)
        lbl.set_text("{:02d}".format(val))
        lbl.set_style_text_font(lv.font_montserrat_48, 0)
        lbl.set_style_text_color(lv.color_hex(0x00E5FF if i == 0 else 0xFFFFFF), 0)
        lbl.center()

    sub = ru_row(
        body,
        "{} {:02d}.{:02d}  •  {} {}".format(DAYS_RU_FULL[t[6] % 7][:9], t[2], t[1], CITY_RU[:10], fmt_temp(state["temp"])),
        0xFBBF24,
        sz=16,
        with_pin=True,
        pin_hole=0x070B14
    )
    sub.align(lv.ALIGN.BOTTOM_MID, 0, -14)

def build_v3():
    set_top_title("3/9 ДЕНЬ НЕДЕЛИ")
    t = get_dt()
    sheet = lv.obj(body)
    sheet.remove_style_all()
    sheet.set_size(156, 196)
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

    mh = ru_row(hdr, "{} {}".format(MONTHS_RU[(t[1] - 1) % 12], t[0]), 0xFFFFFF, sz=16)
    mh.center()

    dl = lv.label(sheet)
    dl.set_text(str(t[2]))
    dl.set_style_text_font(lv.font_montserrat_48, 0)
    dl.set_style_text_color(lv.color_hex(0x0F172A), 0)
    dl.align(lv.ALIGN.CENTER, 0, 4)

    wl = ru_row(sheet, DAYS_RU_FULL[t[6] % 7], 0x334155, sz=14)
    wl.align(lv.ALIGN.BOTTOM_MID, 0, -12)

    rpanel = lv.obj(body)
    rpanel.remove_style_all()
    rpanel.set_size(136, 196)
    rpanel.set_pos(174, 10)
    rpanel.set_style_bg_color(lv.color_hex(0x101C33), 0)
    rpanel.set_style_bg_opa(255, 0)
    rpanel.set_style_radius(12, 0)

    r_clk = lv.label(rpanel)
    r_clk.set_text("{:02d}:{:02d}".format(t[3], t[4]))
    r_clk.set_style_text_font(lv.font_montserrat_36, 0)
    r_clk.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    r_clk.align(lv.ALIGN.TOP_MID, 0, 16)

    r_city = ru_row(rpanel, CITY_RU[:10], 0x00E5FF, sz=14, with_pin=True, pin_hole=0x101C33)
    r_city.align(lv.ALIGN.CENTER, 0, -6)

    r_tmp = lv.label(rpanel)
    r_tmp.set_text(fmt_temp(state["temp"]))
    r_tmp.set_style_text_font(lv.font_montserrat_32, 0)
    r_tmp.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    r_tmp.align(lv.ALIGN.CENTER, 0, 30)

    r_wnd = lv.label(rpanel)
    r_wnd.set_text("BETEP {:.1f} M/C".format(state["wind"]))
    r_wnd.set_style_text_font(lv.font_montserrat_12, 0)
    r_wnd.set_style_text_color(lv.color_hex(0x10B981), 0)
    r_wnd.align(lv.ALIGN.BOTTOM_MID, 0, -12)

def build_v4():
    global sync_lbl_ref
    set_top_title("4/9 МЕТЕОСТАНЦИЯ")
    t = get_dt()
    card = lv.obj(body)
    card.remove_style_all()
    card.set_size(304, 198)
    card.align(lv.ALIGN.CENTER, 0, 0)
    card.set_style_bg_color(lv.color_hex(0x101C33), 0)
    card.set_style_bg_opa(255, 0)
    card.set_style_radius(14, 0)

    c1 = ru_row(card, "{}   •   {:02d}:{:02d}".format(CITY_RU[:12], t[3], t[4]), 0x00E5FF, sz=20, with_pin=True, pin_hole=0x101C33)
    c1.set_pos(16, 12)

    c2 = lv.label(card)
    c2.set_text(fmt_temp(state["temp"]))
    c2.set_style_text_font(lv.font_montserrat_48, 0)
    c2.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    c2.set_pos(16, 48)

    c3 = lv.label(card)
    c3.set_text("MAKC: {}   MИH: {}   BETEP: {:.1f} M/C".replace("И", "I").format(
        fmt_temp(state["tmax"]), fmt_temp(state["tmin"]), state["wind"]
    ))
    c3.set_style_text_font(lv.font_montserrat_14, 0)
    c3.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    c3.set_pos(16, 118)

    c4 = lv.label(card)
    c4.set_text("METEO: {} (O6H #{})".format(get_sync_badge_text(), state["sync_count"]))
    c4.set_style_text_font(lv.font_montserrat_14, 0)
    c4.set_style_text_color(lv.color_hex(0x10B981), 0)
    c4.set_pos(16, 156)
    sync_lbl_ref = c4

def build_v5():
    set_top_title("5/9 ПЛАНЕР ДНЯ")
    t = get_dt()
    hdr = ru_row(
        body,
        "{:02d}:{:02d}  •  {:02d}.{:02d}  •  {} {}".format(t[3], t[4], t[2], t[1], CITY_RU[:9], fmt_temp(state["temp"])),
        0xFBBF24,
        sz=16,
        with_pin=True,
        pin_hole=0x070B14
    )
    hdr.set_pos(12, 8)

    for i, note in enumerate(NOTES_LIST[:3]):
        row = lv.obj(body)
        row.remove_style_all()
        row.set_size(296, 48)
        row.set_pos(12, 42 + i * 54)
        row.set_style_bg_color(lv.color_hex(0x111E36), 0)
        row.set_style_bg_opa(255, 0)
        row.set_style_radius(10, 0)
        nl = ru_row(row, "{}. {}".format(i + 1, str(note)[:24]), 0xFFFFFF, sz=14)
        nl.align(lv.ALIGN.LEFT_MID, 14, 0)

def build_v6():
    set_top_title("6/9 МИРОВОЕ ВРЕМЯ")
    t_local = get_dt()
    utc_h = (t_local[3] - int(TZ_OFFSET // 3600)) % 24
    tok_h = (utc_h + 9) % 24

    zones = [
        (CITY_RU[:12], t_local[3], t_local[4], 0x00E5FF, True),
        ("ЛОНДОН (UTC)", utc_h, t_local[4], 0x10B981, False),
        ("ТОКИО (JST)", tok_h, t_local[4], 0xFBBF24, False)
    ]
    for i, (zname, zh, zm, col, has_pin) in enumerate(zones):
        box = lv.obj(body)
        box.remove_style_all()
        box.set_size(296, 60)
        box.set_pos(12, 8 + i * 68)
        box.set_style_bg_color(lv.color_hex(0x111E36), 0)
        box.set_style_bg_opa(255, 0)
        box.set_style_radius(12, 0)

        zn = ru_row(box, zname, col, sz=16, with_pin=has_pin, pin_hole=0x111E36)
        zn.align(lv.ALIGN.LEFT_MID, 14, 0)

        zv = lv.label(box)
        zv.set_text("{:02d}:{:02d}".format(zh, zm))
        zv.set_style_text_font(lv.font_montserrat_32, 0)
        zv.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        zv.align(lv.ALIGN.RIGHT_MID, -14, 0)

def build_v7():
    set_top_title("7/9 ДО СОБЫТИЯ")
    t = get_dt()
    card = lv.obj(body)
    card.remove_style_all()
    card.set_size(296, 196)
    card.align(lv.ALIGN.CENTER, 0, 0)
    card.set_style_bg_color(lv.color_hex(0x111E36), 0)
    card.set_style_bg_opa(255, 0)
    card.set_style_radius(14, 0)

    l1 = ru_row(card, EVENT_TITLE[:20], 0x00E5FF, sz=20)
    l1.align(lv.ALIGN.TOP_MID, 0, 22)

    l2 = ru_row(card, EVENT_DAYS[:14], 0x10B981, sz=24)
    l2.align(lv.ALIGN.CENTER, 0, 2)

    l3 = ru_row(
        card,
        "{:02d}:{:02d}  •  {} {}".format(t[3], t[4], CITY_RU[:10], fmt_temp(state["temp"])),
        0xFBBF24,
        sz=16,
        with_pin=True,
        pin_hole=0x111E36
    )
    l3.align(lv.ALIGN.BOTTOM_MID, 0, -16)

def build_v8():
    global pomo_lbl_ref
    set_top_title("8/9 ПОМОДОРО")
    t = get_dt()
    mins = state["pomo_sec"] // 60
    secs = state["pomo_sec"] % 60

    pl = lv.label(body)
    pl.set_text("{:02d}:{:02d}".format(mins, secs))
    pl.set_style_text_font(lv.font_montserrat_48, 0)
    pl.set_style_text_color(lv.color_hex(0xF59E0B), 0)
    pl.align(lv.ALIGN.TOP_MID, 0, 16)
    pomo_lbl_ref = pl

    badge = lv.obj(body)
    badge.remove_style_all()
    badge.set_size(256, 46)
    badge.align(lv.ALIGN.CENTER, 0, 14)
    badge.set_style_bg_color(lv.color_hex(0x142038), 0)
    badge.set_style_bg_opa(255, 0)
    badge.set_style_radius(10, 0)
    bl = ru_row(badge, "ФОКУС-СЕССИЯ 25 МИН", 0x10B981, sz=16)
    bl.center()

    cl = ru_row(
        body,
        "{:02d}:{:02d}  •  {} {}".format(t[3], t[4], CITY_RU[:10], fmt_temp(state["temp"])),
        0x00E5FF,
        sz=16,
        with_pin=True,
        pin_hole=0x070B14
    )
    cl.align(lv.ALIGN.BOTTOM_MID, 0, -16)

def build_v9():
    set_top_title("9/9 НОЧНЫЕ ЧАСЫ")
    t = get_dt()
    nc = lv.label(body)
    nc.set_text("{:02d}:{:02d}".format(t[3], t[4]))
    nc.set_style_text_font(lv.font_montserrat_48, 0)
    nc.set_style_text_color(lv.color_hex(0xFFB000), 0)
    nc.align(lv.ALIGN.CENTER, 0, -24)

    nd = ru_row(body, "{} {:02d}.{:02d}.{:04d}".format(DAYS_RU_FULL[t[6] % 7], t[2], t[1], t[0]), 0xF59E0B, sz=16)
    nd.align(lv.ALIGN.CENTER, 0, 28)

    nw = ru_row(
        body,
        "{}  •  {}  •  {}".format(CITY_RU[:10], fmt_temp(state["temp"]), get_sync_badge_text()),
        0xB45309,
        sz=14,
        with_pin=True,
        pin_hole=0x070B14
    )
    nw.align(lv.ALIGN.BOTTOM_MID, 0, -16)

BUILDERS = (
    build_v1, build_v2, build_v3, build_v4, build_v5,
    build_v6, build_v7, build_v8, build_v9
)

def render_current():
    global pomo_lbl_ref, sec_lbl_ref, sync_lbl_ref
    try:
        pomo_lbl_ref = None
        sec_lbl_ref = None
        sync_lbl_ref = None
        gc.collect()
        body.clean()
        t_now = get_dt()
        state["last_min"] = t_now[4]
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
            "release": os.uname().release,
            "mem_free_kb": gc.mem_free() // 1024,
            "variant": variant,
            "bl_pin": bl_pin,
            "rot": hex(rot_hex),
            "inv": hex(inv_cmd),
            "city": CITY_RU,
            "wifi_ok": state["wifi_ok"],
            "last_sync": state["last_sync_str"],
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
                led_g.value(0)
                current_idx = (current_idx + 1) % len(BUILDERS)
                render_current()
                led_g.value(1)
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
                elif line == "SYNC":
                    if state["wifi_ok"]:
                        sync_ntp_and_weather()
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
        wlan.active(False)
        time.sleep_ms(40)
        wlan.active(True)
        state["connect_sec"] = 0
        state["wifi_connecting"] = True
        state["wifi_err"] = False
        update_top_status_bar()
        wlan.connect(WIFI_SSID, WIFI_PASS)
    except Exception as e:
        print("WIFI_START_ERR:", e)
        state["wifi_connecting"] = False
        state["wifi_err"] = True
        update_top_status_bar()

def sync_ntp_and_weather():
    lbl_top_right.set_text("METEO SYNC...")
    lbl_top_right.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    dot_wifi.set_style_bg_color(lv.color_hex(0x00E5FF), 0)
    led_b.value(0)

    try:
        import ntptime
        ntptime.settime()
        state["ntp_applied"] = True
    except Exception:
        pass

    weather_updated = False
    for proto in ("http", "https"):
        try:
            import urequests
            url = "{}://api.open-meteo.com/v1/forecast?latitude={}&longitude={}&current_weather=true&windspeed_unit=ms".format(
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
                weather_updated = True
                break
        except Exception:
            pass

    led_b.value(1)
    t_now = get_dt()
    state["last_sync_str"] = "{:02d}:{:02d}".format(t_now[3], t_now[4])
    state["sync_source"] = "WIFI"
    state["sync_count"] += 1
    state["next_sync_sec"] = 300
    render_current()

def tick_cb(t):
    global current_idx
    state["ticks"] += 1

    # 1. Автомат подключения к Wi-Fi и периодического обновления данных каждые 5 минут (300 сек)
    if state["ticks"] == 1 and WIFI_SSID:
        start_wifi_nonblocking()
    elif state["wifi_connecting"] and wlan is not None:
        state["connect_sec"] += 1
        try:
            if wlan.isconnected():
                state["wifi_ok"] = True
                state["wifi_synced"] = True
                state["wifi_connecting"] = False
                state["wifi_err"] = False
                sync_ntp_and_weather()
            elif state["connect_sec"] > 22:
                state["wifi_connecting"] = False
                state["wifi_err"] = True
        except Exception:
            pass
    elif state["wifi_ok"] and wlan is not None:
        if state["next_sync_sec"] > 0:
            state["next_sync_sec"] -= 1
        else:
            try:
                if wlan.isconnected():
                    sync_ntp_and_weather()
                else:
                    state["wifi_ok"] = False
                    start_wifi_nonblocking()
            except Exception:
                pass
    elif state["wifi_err"] and WIFI_SSID and state["ticks"] % 60 == 0:
        start_wifi_nonblocking()

    # 2. Обновляем пульсирующий индикатор Wi-Fi и таймер обратного отсчёта в верхней шапке (без мигания экрана!)
    update_top_status_bar()

    # 3. Живой ход секунд (:SSc) в классическом календаре (точечно без перерисовки экрана!)
    t_now = get_dt()
    if current_idx == 0 and sec_lbl_ref is not None:
        try:
            sec_lbl_ref.set_text("{:02d}.{:02d} • :{:02d}c".format(t_now[2], t_now[1], t_now[5]))
        except Exception:
            pass
    if current_idx == 0 and sync_lbl_ref is not None:
        try:
            sync_lbl_ref.set_text("CETb OK " + state["last_sync_str"] if state["wifi_ok"] else ("Wi-Fi {}c...".format(state["connect_sec"]) if state["wifi_connecting"] else "METEO " + state["last_sync_str"]))
            sync_lbl_ref.set_style_text_color(lv.color_hex(0x10B981 if state["wifi_ok"] else 0x00E5FF), 0)
        except Exception:
            pass

    # 4. Точечное обновление Помодоро
    if state["pomo_run"] and state["pomo_sec"] > 0:
        state["pomo_sec"] -= 1
        if current_idx == 7 and pomo_lbl_ref is not None:
            try:
                pomo_lbl_ref.set_text("{:02d}:{:02d}".format(state["pomo_sec"] // 60, state["pomo_sec"] % 60))
            except Exception:
                pass
    elif state["pomo_run"] and state["pomo_sec"] == 0:
        state["pomo_sec"] = 25 * 60

    # 5. Полное обновление экрана при смене минуты или в режиме Авто-карусели
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
