#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор образа файловой системы LittleFS v2 (vfs_widgets.bin) для ESP32-2432S024R / S028 (L1435-2.4).
Записывается по адресу 0x343000 (раздел vfs, 189 блоков по 4096 байт).
Хранит конфигурацию в /config.txt (которая патчется прямо в браузере перед прошивкой)
и дублирует чтение из блока 160 (0x3E3000).
"""

import os
from littlefs import LittleFS

BOOT_PY = """# boot.py — ESP32-2432S024R (L1435-2.4) / 2432S028
import gc
import machine

# 1. Изолируем CS тачскрина (GPIO 33) и SD-карты (GPIO 5) в HIGH (1)
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
    b'"eventDays":"73 DAYS","tempC":14,"windMs":3.5}\x00'
).ljust(2048, b" ")

MAIN_PY = """# main.py — ESP32-2432S024R (L1435-2.4) / 2432S028 10 Clocks, Calendars, Weather + Touch
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

# Удерживаем CS=33 и CS=5 в HIGH, гасим красный RGB LED (4, 16, 17 -> 1)
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
    "windMs": 3.5
}

# 1. Читаем конфиг напрямую из файла /config.txt в файловой системе LittleFS
cfg_loaded = False
try:
    with open("/config.txt", "rb") as f:
        raw_file = f.read()
    if raw_file[:8] == b"CYDCFG1:":
        end_idx = raw_file.find(b"\\x00", 8)
        if end_idx > 8:
            loaded = json.loads(bytes(raw_file[8:end_idx]).decode("utf-8"))
            for k in loaded:
                cfg[k] = loaded[k]
            cfg_loaded = True
            print("CYD_CONFIG_FILE_OK:", cfg.get("selectedWidget"), cfg.get("cydVariant"))
except Exception as e:
    print("CYD_CONFIG_FILE_ERR:", e)

# 2. Резервное чтение из сектора 160 (0x3E3000), если /config.txt не был пропатчен
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
            print("CYD_CONFIG_SECTOR_OK:", cfg.get("selectedWidget"), cfg.get("cydVariant"))
except Exception:
    pass

variant = str(cfg.get("cydVariant", "s024_perfect"))

# Настройки специально под матрицу L1435-2.4 (ESP32-2432S024R, подсветка GPIO 27):
# По фото 1 (Профиль 4.3): ориентация rot_hex=0x60 и порядок каналов RGB (use_bgr=False) ИДЕАЛЬНЫ,
# а для тёмного фона (#070B14) вместо белого нужно отправить команду 0x20 (INVOFF) вместо 0x21 (INVON)!
bl_pin = 27
aux_bl_pin = 21
rot_hex = 0x60
use_bgr = False
inv_cmd = 0x20  # 0x20 = INVOFF (тёмный фон #070B14), 0x21 = INVON (инверсия)
byte_swap = 1
spi_freq = 16000000

if variant in ("s024_perfect", "variant4_bl27", "standard"):
    # Профиль 4.1 (Идеальный для вашей платы L1435-2.4): rot=0x60, RGB, INVOFF (0x20) -> Тёмный фон и правильные цвета!
    rot_hex = 0x60
    use_bgr = False
    inv_cmd = 0x20
elif variant == "s024_bgr_inv0":
    # Профиль 4.2: rot=0x60, BGR, INVOFF (0x20) — если синий и красный поменялись местами
    rot_hex = 0x60
    use_bgr = True
    inv_cmd = 0x20
elif variant in ("bl27_st7789", "s024_rgb_inv1"):
    # Профиль 4.3 (как на вашем первом фото — светлый инверсный фон): rot=0x60, RGB, INVON (0x21)
    rot_hex = 0x60
    use_bgr = False
    inv_cmd = 0x21
elif variant in ("bl27_type2_e0", "s024_bgr_inv1"):
    # Профиль 4.4: rot=0x60, BGR, INVON (0x21)
    rot_hex = 0x60
    use_bgr = True
    inv_cmd = 0x21

try:
    machine.Pin(aux_bl_pin, machine.Pin.OUT, value=1)
except Exception:
    pass

print("CYD_DISPLAY_INIT: variant={}, bl_pin={}, rot={}, bgr={}, inv={}".format(
    variant, bl_pin, hex(rot_hex), use_bgr, hex(inv_cmd)
))

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

# Чистая инициализация из Профиля 4.3 (которая дала чёткую картинку без полос на фото 1!),
# но с переключением инверсии 0x20 (INVOFF) для глубокого тёмного фона #070B14!
display.set_params(0x01)  # SWRESET — сбрасывает старые настройки матрицы
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
display.set_params(inv_cmd)  # 0x20 = Тёмный фон, 0x21 = Светлый инверсный фон
display.set_params(0x13)  # NORON
time.sleep_ms(20)
display.set_params(0x29)  # DISPON
time.sleep_ms(50)
display._initilized = True

display.set_rotation(lv.DISPLAY_ROTATION._0)
# Повторно фиксируем MADCTL и INV после set_rotation, чтобы LVGL не перезаписал их
display.set_params(0x36, bytearray([mad_val]))
display.set_params(inv_cmd)
display.set_backlight(100)
try:
    machine.Pin(27, machine.Pin.OUT, value=1)
    machine.Pin(21, machine.Pin.OUT, value=1)
except Exception:
    pass

# Инициализируем резистивный тачскрин XPT2046:
# Поддерживаем ОБЕ разводки плат CYD (SPI1: 14/13/12 и SPI2: 25/32/39) + аппаратный пин касания IRQ = GPIO 36!
touch_dev_spi1 = None
try:
    touch_dev_spi1 = machine.SPI.Device(spi_bus=spi_bus, freq=1000000, cs=33)
except Exception as e:
    print("TOUCH_SPI1_ERR:", e)

pin_touch_irq = machine.Pin(36, machine.Pin.IN)
btn_boot = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)

# Программный опрос второй возможной шины тачскрина (SCK=25, MOSI=32, MISO=39, CS=33)
t_sck = machine.Pin(25, machine.Pin.OUT, value=0)
t_mosi = machine.Pin(32, machine.Pin.OUT, value=0)
t_miso = machine.Pin(39, machine.Pin.IN)

def xpt_soft_transfer(cmd):
    pin_touch_cs.value(0)
    for b in range(8):
        t_mosi.value((cmd >> (7 - b)) & 1)
        t_sck.value(1)
        t_sck.value(0)
    val = 0
    for b in range(16):
        t_sck.value(1)
        val = (val << 1) | (t_miso.value() & 1)
        t_sck.value(0)
    pin_touch_cs.value(1)
    return (val >> 3) & 0xFFF

tx_touch = bytearray([0, 0, 0])
rx_touch = bytearray(3)

def xpt_spi1_transfer(cmd):
    if touch_dev_spi1 is None:
        return 0
    tx_touch[0] = cmd
    tx_touch[1] = 0
    tx_touch[2] = 0
    touch_dev_spi1.write_readinto(tx_touch, rx_touch)
    pin_touch_cs.value(1)
    return (((rx_touch[1] << 8) | rx_touch[2]) >> 3) & 0xFFF

# Активируем PENIRQ (PD1=0, PD0=0 -> пин 36 падает в 0 при касании экрана) на обеих шинах
try:
    xpt_soft_transfer(0x90)
    xpt_spi1_transfer(0x90)
    pin_touch_cs.value(1)
except Exception:
    pass

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
    "wifi_tried": False,
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

    btn2 = lv.button(body)
    btn2.set_size(120, 42)
    btn2.set_pos(170, 82)
    b2l = lv.label(btn2)
    b2l.set_text("RESET 25:00")
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
    try:
        gc.collect()
        body.clean()
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
lbl_nav_mid.set_text("TOUCH / BOOT TO SWITCH")
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
            "board": "ESP32-2432S024R (2.4 inch L1435-2.4)",
            "release": os.uname().release,
            "mem_free_kb": gc.mem_free() // 1024,
            "variant": variant,
            "bl_pin": bl_pin,
            "rot": hex(rot_hex),
            "inv": hex(inv_cmd),
            "touch_type": "Resistive XPT2046 (SPI1 CS=33, IRQ=36)",
            "widget": MODES[current_idx % len(MODES)]
        }
        print("CYD_SCAN_REPORT:" + json.dumps(rep))
    except Exception as e:
        print("CYD_SCAN_ERROR:", e)

print_diag_report()

# Безопасный опрос тачскрина XPT2046 (IRQ=36 + шины 25/32/39 и 14/13/12) и кнопки BOOT (GPIO 0)
last_touch_ms = 0
last_boot_btn = 1
last_irq_val = 1

def poll_touch_and_buttons(t):
    global current_idx, last_touch_ms, last_boot_btn, last_irq_val
    now_ms = time.ticks_ms()

    # 1. Физическая кнопка BOOT (GPIO 0) на плате
    try:
        b_val = btn_boot.value()
        if b_val == 0 and last_boot_btn == 1:
            current_idx = (current_idx + 1) % len(BUILDERS)
            render_current()
            last_touch_ms = now_ms
        last_boot_btn = b_val
    except Exception:
        pass

    # 2. Резистивный тачскрин XPT2046: опрашиваем шину ТОЛЬКО когда палец касается стекла (GPIO 36 == 0)!
    # В покое CS=33 всегда равен 1 (HIGH), поэтому на экране гарантированно 0 помех и 0 полос!
    if time.ticks_diff(now_ms, last_touch_ms) > 360:
        try:
            if pin_touch_irq.value() == 0:
                last_touch_ms = now_ms
                led_g.value(0)
                x_soft = xpt_soft_transfer(0xD0)
                y_soft = xpt_soft_transfer(0x90)
                xpt_soft_transfer(0x90)  # Перевзводим PENIRQ (PD0=0)
                x_spi1 = xpt_spi1_transfer(0xD0)
                y_spi1 = xpt_spi1_transfer(0x90)
                xpt_spi1_transfer(0x90)  # Перевзводим PENIRQ (PD0=0)
                pin_touch_cs.value(1)

                raw_x = x_soft if (100 < x_soft < 3950) else x_spi1
                raw_y = y_soft if (100 < y_soft < 3950) else y_spi1

                if current_idx == 7 and 1100 < raw_x < 2900 and 1100 < raw_y < 2900:
                    state["pomo_run"] = not state["pomo_run"]
                    render_current()
                else:
                    if 100 < raw_x < 1900:
                        current_idx = (current_idx - 1) % len(BUILDERS)
                    else:
                        current_idx = (current_idx + 1) % len(BUILDERS)
                    render_current()
                led_g.value(1)
        except Exception:
            pin_touch_cs.value(1)

timer_touch = lv.timer_create(poll_touch_and_buttons, 100, None)
timer_touch.set_repeat_count(-1)

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
            for _ in range(15):
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

poll_in = select.poll()
poll_in.register(sys.stdin, select.POLLIN)
s_buf = ""

def tick_cb(t):
    global current_idx, s_buf
    state["ticks"] += 1
    if state["ticks"] == 2 and WIFI_SSID and not state["wifi_tried"]:
        state["wifi_tried"] = True
        connect_wifi_and_fetch()

    if state["pomo_run"] and state["pomo_sec"] > 0:
        state["pomo_sec"] -= 1
        if current_idx == 7:
            render_current()

    if AUTO_CAROUSEL and state["ticks"] % 10 == 0:
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
