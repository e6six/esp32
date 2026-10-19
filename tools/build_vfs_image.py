#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор образа файловой системы LittleFS v2 (vfs_widgets.bin) для дисплея L i 435-2 4 (ESP32-2432S024R / S028).
Записывается по адресу 0x343000 (раздел vfs, 189 блоков по 4096 байт).
- Полностью убран опрос плавающего пина GPIO 36 и CS=33 (больше никаких самопроизвольных переключений и мерцаний!).
- Переключение виджетов: в 1 клик с сайта ИЛИ физической кнопкой BOOT (GPIO 0) на плате.
- Реальное время (RTC) и живая погода Open-Meteo передаются прямо из браузера в момент прошивки + обновляются по Wi-Fi в фоне!
"""

import os
from littlefs import LittleFS

BOOT_PY = """# boot.py — ESP32-2432S024R (L i 435-2 4)
import gc
import machine

# 1. Изолируем CS SD-карты (GPIO 5) в HIGH (1). Пин 33 оставляем аппаратному драйверу SPI тачскрина XPT2046!
try:
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

MAIN_PY = """# main.py — ESP32-2432S024R (L i 435-2 4) 10 Clocks, Calendars & Live Weather (Zero Flicker)
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

# Держим CS=5 (SD-карта) в HIGH (1). Пин CS=33 передаём аппаратному SPI-устройству тачскрина XPT2046!
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

# 1. Читаем конфиг из файла /config.txt в файловой системе LittleFS
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

# 2. Резервное чтение из сектора 160 (0x3E3000)
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

# Устанавливаем точное реальное время ПК в аппаратные часы RTC ESP32 сразу при старте!
# Формат machine.RTC().datetime(): (year, month, day, weekday, hours, minutes, seconds, subseconds)
rtc_synced_from_pc = False
try:
    rt = cfg.get("rtcTuple")
    if isinstance(rt, list) and len(rt) >= 7:
        machine.RTC().datetime((int(rt[0]), int(rt[1]), int(rt[2]), int(rt[3]), int(rt[4]), int(rt[5]), int(rt[6]), 0))
        rtc_synced_from_pc = True
        print("CYD_RTC_SET_FROM_PC:", rt)
except Exception as e:
    print("CYD_RTC_ERR:", e)

variant = str(cfg.get("cydVariant", "s024_perfect"))

# Настройки под матрицу L i 435-2 4 (2.4", подсветка GPIO 27):
bl_pin = 27
aux_bl_pin = 21
rot_hex = 0x60
use_bgr = False
inv_cmd = 0x20  # 0x20 = INVOFF (тёмный фон #070B14), 0x21 = INVON (инверсия)
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

display.set_params(0x01)  # SWRESET
time.sleep_ms(120)
display.set_params(0x11)  # SLPOUT
time.sleep_ms(120)
display.set_params(0x3A, bytearray([0x55]))  # 16-bit RGB565
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
display.set_params(0x13)  # NORON
time.sleep_ms(20)
display.set_params(0x29)  # DISPON
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

# Инициализируем резистивный тачскрин U3 XPT2046 по заводской схеме ESP32-2432S024:
# TP_CLK=IO14, TP_DIN=IO13, TP_OUT=IO12 (общая шина spi_bus), TP_CS=IO33, TP_IRQ=IO36 (с подтяжкой R3=10k к 3.3V)
touch_dev = None
tx_touch = bytearray([0x90, 0x00, 0x00])
rx_touch = bytearray(3)
try:
    touch_dev = machine.SPI.Device(spi_bus=spi_bus, freq=2000000, cs=33)
    # Отправляем 0x90 (PD1=0, PD0=0), чтобы активировать выход /PENIRQ (IO36) в XPT2046
    touch_dev.write_readinto(tx_touch, rx_touch)
except Exception as e:
    print("TOUCH_INIT_ERR:", e)

pin_touch_irq = machine.Pin(36, machine.Pin.IN)
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
    "pomo_run": False,
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
lbl_top_right.set_text(CITY_NAME[:10] + (" (SYNC)" if rtc_synced_from_pc else ""))
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

# Если время синхронизировано по NTP (UTC), прибавляем TZ_OFFSET; если задано напрямую с ПК — уже локальное!
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

def build_v1():
    lbl_top_left.set_text("1/9 CLASSIC CALENDAR")
    t = get_dt()

    left = lv.obj(body)
    left.remove_style_all()
    left.set_size(126, 174)
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
    wb.set_size(122, 80)
    wb.set_pos(2, 86)
    wb.set_style_bg_color(lv.color_hex(0x111E36), 0)
    wb.set_style_bg_opa(255, 0)
    wb.set_style_radius(8, 0)

    wl = lv.label(wb)
    wl.set_text("{}\\n{}\\nWind {:.1f} m/s".format(CITY_NAME[:12], fmt_temp(state["temp"]), state["wind"]))
    wl.set_style_text_font(lv.font_montserrat_14, 0)
    wl.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    wl.align(lv.ALIGN.CENTER, 0, 0)

    cbox = lv.obj(body)
    cbox.remove_style_all()
    cbox.set_size(180, 170)
    cbox.set_pos(134, 6)
    cbox.set_style_bg_color(lv.color_hex(0x0D1526), 0)
    cbox.set_style_bg_opa(255, 0)
    cbox.set_style_radius(8, 0)

    mhdr = lv.label(cbox)
    mhdr.set_text("{} {}".format(MONTHS_EN[(t[1]-1)%12], t[0]))
    mhdr.set_style_text_font(lv.font_montserrat_12, 0)
    mhdr.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    mhdr.align(lv.ALIGN.TOP_MID, 0, 6)

    first_col = dow_mon_first(t[0], t[1], 1)
    tot_days = days_in_month(t[0], t[1])
    lines = ["Mo Tu We Th Fr Sa Su"]
    cur_line = "   " * first_col
    col = first_col
    for d in range(1, tot_days + 1):
        if d == t[2]:
            cur_line += "[{:d}]".format(d)
        else:
            cur_line += "{:2d} ".format(d)
        col += 1
        if col >= 7:
            lines.append(cur_line.rstrip())
            cur_line = ""
            col = 0
    if cur_line.strip():
        lines.append(cur_line.rstrip())

    grid_lbl = lv.label(cbox)
    grid_lbl.set_text("\\n".join(lines))
    grid_lbl.set_style_text_font(lv.font_montserrat_12, 0)
    grid_lbl.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    grid_lbl.set_pos(8, 26)

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
    global pomo_lbl_ref
    lbl_top_left.set_text("8/9 POMODORO & CLOCK")
    t = get_dt()
    mins = state["pomo_sec"] // 60
    secs = state["pomo_sec"] % 60

    pl = lv.label(body)
    pl.set_text("{:02d}:{:02d}".format(mins, secs))
    pl.set_style_text_font(lv.font_montserrat_48, 0)
    pl.set_style_text_color(lv.color_hex(0xF59E0B), 0)
    pl.align(lv.ALIGN.TOP_MID, 0, 14)
    pomo_lbl_ref = pl

    btn1 = lv.button(body)
    btn1.set_size(120, 42)
    btn1.set_pos(30, 82)
    b1l = lv.label(btn1)
    b1l.set_text("RUNNING" if state["pomo_run"] else "READY 25:00")
    b1l.center()

    btn2 = lv.button(body)
    btn2.set_size(120, 42)
    btn2.set_pos(170, 82)
    b2l = lv.label(btn2)
    b2l.set_text("FOCUS MODE")
    b2l.center()

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

btn_prev = lv.button(nav)
btn_prev.set_size(88, 26)
btn_prev.align(lv.ALIGN.LEFT_MID, 8, 0)
lp = lv.label(btn_prev)
lp.set_text("< PREV")
lp.set_style_text_font(lv.font_montserrat_12, 0)
lp.center()

lbl_nav_mid = lv.label(nav)
lbl_nav_mid.set_text("TOUCH < PREV | NEXT >")
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

# Чтение регистра XPT2046 по аппаратному SPI (CS=33 управляется драйвером ESP-IDF)
def read_xpt(cmd):
    if touch_dev is None:
        return 0
    tx_touch[0] = cmd
    tx_touch[1] = 0
    tx_touch[2] = 0
    touch_dev.write_readinto(tx_touch, rx_touch)
    return (((rx_touch[1] << 8) | rx_touch[2]) >> 3) & 0xFFF

# Опрос тачскрина XPT2046 (ТОЛЬКО когда палец нажал на экран и IO36 == 0!) и кнопки BOOT (GPIO 0)
boot_hold_cnt = 0
touch_released = True
last_switch_ms = 0

def poll_touch_and_boot(t):
    global current_idx, boot_hold_cnt, touch_released, last_switch_ms
    now_ms = time.ticks_ms()

    # 1. Физическая кнопка BOOT (GPIO 0)
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

    # 2. Резистивный тачскрин U3 XPT2046 (по схеме ESP32-2432S024: IO36 = /PENIRQ с подтяжкой R3=10k к 3.3V)
    # В покое IO36 == 1 -> шина SPI1 НЕ опрашивается вообще (0 мерцаний экрана!)
    if touch_dev is None:
        return
    try:
        if pin_touch_irq.value() != 0:
            touch_released = True
            return

        # Если палец ещё не отпущен после прошлого переключения или прошло < 320 мс — ждём отпускания
        if not touch_released or time.ticks_diff(now_ms, last_switch_ms) < 320:
            return

        # Холостое чтение 0xB1 для заряда фильтрующих конденсаторов C18..C21 (1 нФ по схеме) + проверка устойчивости
        read_xpt(0xB1)
        time.sleep_ms(4)
        if pin_touch_irq.value() != 0:
            return

        z1 = read_xpt(0xB1)
        z2 = read_xpt(0xC1)
        # Настоящее нажатие пальцем даёт z1 > 400 и z2 < 3800 (отсекает 100% наводок и заряд 1нФ конденсаторов)
        if z1 > 400 and z2 < 3800:
            y1 = read_xpt(0x91)
            y2 = read_xpt(0x91)
            x1 = read_xpt(0xD1)
            x2 = read_xpt(0xD0)  # Команда 0xD0 (PD1=0, PD0=0) читает X2 и снова включает /PENIRQ на IO36!
            if abs(y1 - y2) < 250 and abs(x1 - x2) < 250:
                touch_released = False
                last_switch_ms = now_ms
                led_g.value(0)

                # В альбомной развёртке 0x60 (MV=1) горизонтальная ось 320px (< PREV .. NEXT >) — это Y (0x90),
                # но если край гибкого шлейфа инвертирован, проверяем обе координаты:
                horiz = y1 if abs(y1 - 2048) >= abs(x1 - 2048) else x1
                if current_idx == 7 and 1300 < y1 < 2800 and 1300 < x1 < 2800:
                    state["pomo_run"] = not state["pomo_run"]
                    render_current()
                else:
                    if horiz < 2048:
                        current_idx = (current_idx - 1) % len(BUILDERS)
                    else:
                        current_idx = (current_idx + 1) % len(BUILDERS)
                    render_current()
                lbl_nav_mid.set_text("MODE {}/9".format(current_idx + 1))
                led_g.value(1)
        else:
            # Перевзводим /PENIRQ (PD1=0, PD0=0)
            read_xpt(0x90)
    except Exception:
        pass

timer_btn = lv.timer_create(poll_touch_and_boot, 70, None)
timer_btn.set_repeat_count(-1)

# Неблокирующее подключение к Wi-Fi и загрузка живой погоды Open-Meteo + NTP времени
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
        print("CYD_NTP_OK")
    except Exception as e:
        print("CYD_NTP_ERR:", e)

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
                print("CYD_WEATHER_OK:", t_now)
                break
        except Exception as e:
            print("CYD_WEATHER_ERR:", proto, e)

    lbl_top_right.set_text("WIFI OK " + fmt_temp(state["temp"]))
    render_current()

poll_in = select.poll()
poll_in.register(sys.stdin, select.POLLIN)
s_buf = ""

def tick_cb(t):
    global current_idx, s_buf
    state["ticks"] += 1

    # 1. Неблокирующий автомат подключения к Wi-Fi (ждёт сколько нужно: от 1 до 25 секунд)
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
                lbl_top_right.set_text(CITY_NAME[:10] + " (SYNC)")
        except Exception:
            pass
    elif state["wifi_synced"] and state["ticks"] % 900 == 0 and wlan is not None:
        try:
            if wlan.isconnected():
                sync_ntp_and_weather()
        except Exception:
            pass

    # 2. Обновляем Помодоро-таймер точечно без очистки экрана (без мерцания!)
    if state["pomo_run"] and state["pomo_sec"] > 0:
        state["pomo_sec"] -= 1
        if current_idx == 7 and pomo_lbl_ref is not None:
            try:
                pomo_lbl_ref.set_text("{:02d}:{:02d}".format(state["pomo_sec"] // 60, state["pomo_sec"] % 60))
            except Exception:
                pass

    # 3. Перерисовываем экран ТОЛЬКО при смене минуты (никаких 30-секундных миганий!) или в режиме Авто-карусели (10/10)
    t_now = get_dt()
    if AUTO_CAROUSEL and state["ticks"] % 15 == 0:
        current_idx = (current_idx + 1) % len(BUILDERS)
        render_current()
    elif t_now[4] != state["last_min"]:
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
