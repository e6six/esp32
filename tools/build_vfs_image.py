#!/usr/bin/env python3
"""
Генератор файловой системы LittleFS v2 (vfs_widgets.bin) для ESP32-2432S024 / S028 (CYD).
Собирает образ раздела `vfs` (смещение 0x343000, размер 0x0BD000 = 189 блоков по 4096 байт):
  - /boot.py      : Изоляция CS тачскрина (GPIO 33) и SD-карты (GPIO 5), гашение RGB LED
  - /config.txt   : Выровненный JSON-конфиг с маркером CYDCFG1: (2048 байт) для патчинга в браузере
  - /ru_12.bin    : Кириллический шрифт Montserrat SemiBold 12px + иконки FontAwesome 5 (📍, ☀, ☁, 💨, 📶)
  - /ru_14.bin    : Кириллический шрифт Montserrat SemiBold 14px + иконки FontAwesome 5
  - /ru_16.bin    : Кириллический шрифт Montserrat SemiBold 16px + иконки FontAwesome 5
  - /ru_24.bin    : Кириллический шрифт Montserrat SemiBold 24px + иконки FontAwesome 5
  - /main.py      : Движок 10 виджетов 320x240 на русском языке + бесплатные метеостанции (Open-Meteo / MET Norway)
"""

import os
import json
from littlefs import LittleFS

DEFAULT_CFG = {
    "wifiSsid": "",
    "wifiPass": "",
    "cityName": "Бутово",
    "latitude": 55.5383,
    "longitude": 37.5619,
    "timezoneOffset": 3,
    "weatherStation": "open_meteo",
    "tempC": 14,
    "tmaxC": 17,
    "tminC": 9,
    "windMs": 3.2,
    "humidity": 64,
    "weatherCode": 2,
    "selectedWidget": "v1_classic_cal",
    "cydVariant": "s024_perfect",
    "rtcTuple": [2026, 10, 20, 1, 14, 30, 0, 0],
    "notes": [
        "Проверить погоду в Бутово",
        "Синхронизация метеостанции",
        "Отличного рабочего дня!"
    ],
    "eventTitle": "НОВЫЙ ГОД",
    "eventDays": "73 ДНЯ"
}

raw_cfg = "CYDCFG1:" + json.dumps(DEFAULT_CFG, ensure_ascii=False) + "\x00"
raw_cfg_bytes = raw_cfg.encode("utf-8")
assert len(raw_cfg_bytes) <= 2048
DEFAULT_CFG_BYTES = raw_cfg_bytes + (b" " * (2048 - len(raw_cfg_bytes)))

BOOT_PY = """# boot.py - CYD ESP32-2432S024R / S028R Hardware Init
import gc
import machine

try:
    machine.freq(240000000)
except Exception:
    pass

# Строго держим CS тачскрина (GPIO 33) и SD-карты (GPIO 5) в HIGH (неактивны),
# чтобы они не мешали шине SPI дисплея и экран не мерцал
for _cs_pin in (33, 5):
    try:
        machine.Pin(_cs_pin, machine.Pin.OUT, value=1)
    except Exception:
        pass

# Гасим яркий передний RGB-светодиод (Active LOW -> 1 = ВЫКЛ)
for _rgb_pin in (4, 16, 17):
    try:
        machine.Pin(_rgb_pin, machine.Pin.OUT, value=1)
    except Exception:
        pass

gc.collect()
"""

MAIN_PY = """# main.py - Движок 10 настольных виджетов для ESP32-2432S024 / S028 (CYD 320x240)
import gc
import os
import sys
import time
import json
import select
import machine
import lvgl as lv
import lcd_bus
import ili9341
import task_handler

gc.collect()

# 1. Инициализация пинов RGB LED (Active LOW) и кнопки BOOT (GPIO 0)
led_r = machine.Pin(4, machine.Pin.OUT, value=1)
led_g = machine.Pin(16, machine.Pin.OUT, value=1)
led_b = machine.Pin(17, machine.Pin.OUT, value=1)
btn_boot = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)

# Изолируем CS других устройств на плате (Touch CS=33, SD CS=5) -> 0% мерцания экрана
pin_touch_cs = machine.Pin(33, machine.Pin.OUT, value=1)
pin_sd_cs = machine.Pin(5, machine.Pin.OUT, value=1)

# 2. Загрузка конфигурации (приоритет: прямой сектор 160 флеш-памяти или /config.txt)
cfg = {}
try:
    from flashbdev import bdev
    raw = bytearray(2048)
    bdev.readblocks(160, raw)
    if raw[:8] == b"CYDCFG1:":
        end_idx = raw.find(b"\\x00", 8)
        if end_idx != -1:
            cfg = json.loads(raw[8:end_idx].decode("utf-8"))
except Exception as e:
    print("RAW_CFG_ERR:", e)

if not cfg:
    try:
        with open("/config.txt", "rb") as f:
            data = f.read()
        if data.startswith(b"CYDCFG1:"):
            end_idx = data.find(b"\\x00", 8)
            if end_idx != -1:
                cfg = json.loads(data[8:end_idx].decode("utf-8"))
    except Exception as e:
        print("FILE_CFG_ERR:", e)

# 3. Установка точного времени из браузера в аппаратные часы RTC ESP32
try:
    rt = cfg.get("rtcTuple")
    if isinstance(rt, list) and len(rt) == 8:
        machine.RTC().datetime(tuple(rt))
except Exception as e:
    print("RTC_SET_ERR:", e)

# 4. Выбор профиля экрана (по умолчанию: проверенный профиль 4.1 для L i 435-2 4)
variant = str(cfg.get("cydVariant", "s024_perfect"))
bl_pin = 27
rot_hex = 0x60
use_bgr = False
inv_cmd = 0x20

if variant == "s024_rot180_rgb_noinv":
    bl_pin, rot_hex, use_bgr, inv_cmd = 27, 0xA0, False, 0x20
elif variant == "s024_rot0_bgr_noinv":
    bl_pin, rot_hex, use_bgr, inv_cmd = 27, 0x60, True, 0x20
elif variant == "s024_rot180_bgr_noinv":
    bl_pin, rot_hex, use_bgr, inv_cmd = 27, 0xA0, True, 0x20
elif variant == "s024_rot0_rgb_inv":
    bl_pin, rot_hex, use_bgr, inv_cmd = 27, 0x60, False, 0x21
elif variant == "s028_classic":
    bl_pin, rot_hex, use_bgr, inv_cmd = 21, 0x60, False, 0x20
elif variant == "s024_mirror_fix":
    bl_pin, rot_hex, use_bgr, inv_cmd = 27, 0x20, False, 0x20
elif variant == "s024_flip_y":
    bl_pin, rot_hex, use_bgr, inv_cmd = 27, 0xE0, False, 0x20

# 5. Инициализация выделенной шины SPI только для дисплея (16 МГц - идеальная стабильность)
spi_freq = 16000000
spi_bus = machine.SPI.Bus(host=1, mosi=13, miso=12, sck=14)
display_bus = lcd_bus.SPIBus(
    spi_bus=spi_bus,
    freq=spi_freq,
    dc=2,
    cs=15
)

display = ili9341.ILI9341(
    data_bus=display_bus,
    display_width=320,
    display_height=240,
    backlight_pin=bl_pin,
    backlight_on_state=ili9341.STATE_HIGH,
    color_space=lv.COLOR_FORMAT.RGB565,
    color_byte_order=ili9341.BYTE_ORDER_BGR if use_bgr else ili9341.BYTE_ORDER_RGB,
    rgb565_byte_swap=True
)

display._ORIENTATION_TABLE = (rot_hex, 0x0, 0x0, 0x0)
display.set_power(True)

# Проверенный гибридный init для контроллера L i 435-2 4 (ST7789 / ILI9341)
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

th = task_handler.TaskHandler()

# 6. Загрузка русских бинарных шрифтов LVGL (Montserrat SemiBold Кириллица + FontAwesome 5)
FONT_12 = lv.font_montserrat_12
FONT_14 = lv.font_montserrat_14
FONT_16 = lv.font_montserrat_16
FONT_24 = lv.font_montserrat_24
FONT_28 = lv.font_montserrat_28
FONT_32 = lv.font_montserrat_32
FONT_36 = lv.font_montserrat_36
FONT_40 = lv.font_montserrat_40
FONT_48 = lv.font_montserrat_48
RU_OK = False

try:
    import fs_driver
    fs_font_driver = lv.fs_drv_t()
    fs_driver.fs_register(fs_font_driver, 'S')

    def _load_binfont(fname):
        gc.collect()
        f = lv.binfont_create('S:' + fname)
        if not f:
            f = lv.binfont_create('S:/' + fname)
        gc.collect()
        return f

    f12 = _load_binfont("ru_12.bin")
    f14 = _load_binfont("ru_14.bin")
    f16 = _load_binfont("ru_16.bin")
    f24 = _load_binfont("ru_24.bin")
    if f12 and f14 and f16 and f24:
        FONT_12 = f12
        FONT_14 = f14
        FONT_16 = f16
        FONT_24 = f24
        RU_OK = True
except Exception as e:
    print("RU_FONT_ERR:", e)

# Иконки FontAwesome 5 Solid (встроены в ru_12..ru_24)
IC_PIN   = "\\uf3c5" if RU_OK else "*"
IC_WIFI  = "\\uf1eb" if RU_OK else ""
IC_SYNC  = "\\uf021" if RU_OK else ""
IC_SUN   = "\\uf185" if RU_OK else ""
IC_CSUN  = "\\uf6c4" if RU_OK else ""
IC_CLD   = "\\uf0c2" if RU_OK else ""
IC_RAIN  = "\\uf73d" if RU_OK else ""
IC_SNOW  = "\\uf2dc" if RU_OK else ""
IC_WIND  = "\\uf72e" if RU_OK else ""
IC_OK    = "\\uf00c" if RU_OK else ""
DEG      = "°C" if RU_OK else " C"

WIFI_SSID = str(cfg.get("wifiSsid", "")).strip()
WIFI_PASS = str(cfg.get("wifiPass", ""))
CITY_NAME = str(cfg.get("cityName", "Бутово" if RU_OK else "Butovo"))
CITY_LAT = float(cfg.get("latitude", 55.5383))
CITY_LON = float(cfg.get("longitude", 37.5619))
WEATHER_STATION = str(cfg.get("weatherStation", "open_meteo"))
TZ_OFFSET = int(float(cfg.get("timezoneOffset", 3)) * 3600)
START_WIDGET = str(cfg.get("selectedWidget", "v1_classic_cal"))
AUTO_CAROUSEL = (START_WIDGET == "v10_carousel")
NOTES_LIST = cfg.get("notes", ["Проверить погоду", "Синхронизация", "Отличного дня!"])
EVENT_TITLE = str(cfg.get("eventTitle", "НОВЫЙ ГОД" if RU_OK else "NEW YEAR"))
EVENT_DAYS = str(cfg.get("eventDays", "73 ДНЯ" if RU_OK else "73 DAYS"))

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
    "wcode": int(cfg.get("weatherCode", 2)),
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

DAYS_FULL = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"] if RU_OK else ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"] if RU_OK else ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
MONTHS_FULL = ["ЯНВАРЬ", "ФЕВРАЛЬ", "МАРТ", "АПРЕЛЬ", "МАЙ", "ИЮНЬ", "ИЮЛЬ", "АВГУСТ", "СЕНТЯБРЬ", "ОКТЯБРЬ", "НОЯБРЬ", "ДЕКАБРЬ"] if RU_OK else ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"] if RU_OK else ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def get_weather_icon(code):
    if not RU_OK:
        return ""
    if code == 0:
        return IC_SUN
    if code in (1, 2):
        return IC_CSUN
    if code in (3, 45, 48):
        return IC_CLD
    if code in (71, 73, 75, 77, 85, 86):
        return IC_SNOW
    return IC_RAIN

def get_weather_desc(code):
    if not RU_OK:
        return "Clear" if code == 0 else ("Cloudy" if code <= 3 else "Rain")
    if code == 0:
        return "Ясно"
    if code in (1, 2):
        return "Перем. облачность"
    if code in (3, 45, 48):
        return "Пасмурно"
    if code in (71, 73, 75, 77, 85, 86):
        return "Снегопад"
    return "Дождь"

scr = lv.screen_active()
scr.set_style_bg_color(lv.color_hex(0x070B14), 0)
scr.set_style_bg_opa(255, 0)
scr.remove_flag(lv.obj.FLAG.SCROLLABLE)

# Верхняя панель статуса (24px): слева название режима, справа индикатор Wi-Fi + точка-пульс + время обновления
top = lv.obj(scr)
top.remove_style_all()
top.set_size(320, 24)
top.set_pos(0, 0)
top.set_style_bg_color(lv.color_hex(0x101C33), 0)
top.set_style_bg_opa(255, 0)

lbl_top_left = lv.label(top)
lbl_top_left.set_text("1/9 КАЛЕНДАРЬ" if RU_OK else "1/9 CALENDAR")
lbl_top_left.set_style_text_color(lv.color_hex(0x00E5FF), 0)
lbl_top_left.set_style_text_font(FONT_12, 0)
lbl_top_left.align(lv.ALIGN.LEFT_MID, 6, 0)

dot_wifi = lv.obj(top)
dot_wifi.remove_style_all()
dot_wifi.set_size(8, 8)
dot_wifi.set_style_radius(4, 0)
dot_wifi.set_style_bg_color(lv.color_hex(0x00E5FF), 0)
dot_wifi.set_style_bg_opa(255, 0)
dot_wifi.align(lv.ALIGN.RIGHT_MID, -6, 0)

lbl_top_right = lv.label(top)
if WIFI_SSID:
    lbl_top_right.set_text("Wi-Fi: старт..." if RU_OK else "Wi-Fi: init...")
    lbl_top_right.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    dot_wifi.set_style_bg_color(lv.color_hex(0xFBBF24), 0)
else:
    lbl_top_right.set_text(("USB СИНХР " if RU_OK else "USB SYNC ") + state["last_sync_str"])
    lbl_top_right.set_style_text_color(lv.color_hex(0x38BDF8), 0)
    dot_wifi.set_style_bg_color(lv.color_hex(0x38BDF8), 0)
lbl_top_right.set_style_text_font(FONT_12, 0)
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
    return ("+{:.0f}" + DEG if v > 0 else "{:.0f}" + DEG).format(v)

def get_sync_badge_text():
    if state["wifi_connecting"]:
        return ("Wi-Fi ({}с)..." if RU_OK else "Wi-Fi ({}s)...").format(state["connect_sec"])
    if state["wifi_ok"]:
        return ("WIFI ОК • " if RU_OK else "WIFI OK | ") + state["last_sync_str"]
    if state["wifi_err"]:
        return ("СБОЙ WIFI • " if RU_OK else "WIFI ERR | ") + state["last_sync_str"]
    return ("USB СИНХР • " if RU_OK else "USB OK | ") + state["last_sync_str"]

def update_top_status_bar():
    pulse_on = (state["ticks"] % 2 == 0)
    if state["wifi_connecting"]:
        lbl_top_right.set_text(("Wi-Fi... {}с" if RU_OK else "Wi-Fi... {}s").format(state["connect_sec"]))
        lbl_top_right.set_style_text_color(lv.color_hex(0xFBBF24), 0)
        dot_wifi.set_style_bg_color(lv.color_hex(0xFBBF24 if pulse_on else 0x78350F), 0)
    elif state["wifi_ok"]:
        rem_m = state["next_sync_sec"] // 60
        rem_s = state["next_sync_sec"] % 60
        lbl_top_right.set_text(
            ("WIFI ОК | Обн {} ({:d}:{:02d})" if RU_OK else "WIFI OK | Upd {} ({:d}:{:02d})").format(
                state["last_sync_str"], rem_m, rem_s
            )
        )
        lbl_top_right.set_style_text_color(lv.color_hex(0x10B981), 0)
        dot_wifi.set_style_bg_color(lv.color_hex(0x10B981 if pulse_on else 0x064E3B), 0)
    elif state["wifi_err"]:
        lbl_top_right.set_text(("СБОЙ WIFI | USB {}" if RU_OK else "WIFI ERR | USB {}").format(state["last_sync_str"]))
        lbl_top_right.set_style_text_color(lv.color_hex(0xFB7185), 0)
        dot_wifi.set_style_bg_color(lv.color_hex(0xEF4444 if pulse_on else 0x7F1D1D), 0)
    else:
        lbl_top_right.set_text(("USB СИНХР | {}" if RU_OK else "USB SYNC | {}").format(state["last_sync_str"]))
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

# 1. КЛАССИЧЕСКИЙ КАЛЕНДАРЬ + КРУПНЫЕ ЧАСЫ + ПИНЫ 📍 БУТОВО НА РУССКОМ (1-в-1 с предпросмотром)
def build_v1():
    global sec_lbl_ref, sync_lbl_ref
    lbl_top_left.set_text("1/9 КАЛЕНДАРЬ" if RU_OK else "1/9 CALENDAR")
    t = get_dt()

    left = lv.obj(body)
    left.remove_style_all()
    left.set_size(120, 208)
    left.set_pos(4, 4)

    clk = lv.label(left)
    clk.set_text("{:02d}:{:02d}".format(t[3], t[4]))
    clk.set_style_text_font(FONT_40, 0)
    clk.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    clk.set_pos(2, 0)

    day_lbl = lv.label(left)
    day_lbl.set_text(("{} :{:02d}с" if RU_OK else "{} :{:02d}s").format(DAYS_FULL[t[6] % 7][:9], t[5]))
    day_lbl.set_style_text_font(FONT_14, 0)
    day_lbl.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    day_lbl.set_pos(4, 46)
    sec_lbl_ref = day_lbl

    dt_lbl = lv.label(left)
    dt_lbl.set_text("{} {}".format(t[2], MONTHS_GEN[(t[1] - 1) % 12]))
    dt_lbl.set_style_text_font(FONT_14, 0)
    dt_lbl.set_style_text_color(lv.color_hex(0xCBD5E1), 0)
    dt_lbl.set_pos(4, 66)

    wb = lv.obj(left)
    wb.remove_style_all()
    wb.set_size(116, 116)
    wb.set_pos(2, 90)
    wb.set_style_bg_color(lv.color_hex(0x111E36), 0)
    wb.set_style_bg_opa(255, 0)
    wb.set_style_radius(10, 0)

    w_city = lv.label(wb)
    w_city.set_text("{} {}".format(IC_PIN, CITY_NAME[:11]))
    w_city.set_style_text_font(FONT_14, 0)
    w_city.set_style_text_color(lv.color_hex(0x38BDF8), 0)
    w_city.align(lv.ALIGN.TOP_MID, 0, 6)

    w_temp = lv.label(wb)
    w_temp.set_text("{} {}".format(get_weather_icon(state["wcode"]), fmt_temp(state["temp"])).strip())
    w_temp.set_style_text_font(FONT_24, 0)
    w_temp.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    w_temp.align(lv.ALIGN.CENTER, 0, -4)

    w_wind = lv.label(wb)
    w_wind.set_text(("Ветер {:.1f} м/с" if RU_OK else "Wind {:.1f} m/s").format(state["wind"]))
    w_wind.set_style_text_font(FONT_12, 0)
    w_wind.set_style_text_color(lv.color_hex(0xCBD5E1), 0)
    w_wind.align(lv.ALIGN.BOTTOM_MID, 0, -24)

    w_sync = lv.label(wb)
    w_sync.set_text(get_sync_badge_text())
    w_sync.set_style_text_font(FONT_12, 0)
    w_sync.set_style_text_color(lv.color_hex(0x10B981 if state["wifi_ok"] else 0x00E5FF), 0)
    w_sync.align(lv.ALIGN.BOTTOM_MID, 0, -6)
    sync_lbl_ref = w_sync

    # Правая панель (190 x 208): ИДЕАЛЬНО РОВНАЯ СЕТКА КАЛЕНДАРЯ (7 колонок по 26px)
    cbox = lv.obj(body)
    cbox.remove_style_all()
    cbox.set_size(190, 208)
    cbox.set_pos(126, 4)
    cbox.set_style_bg_color(lv.color_hex(0x0D1526), 0)
    cbox.set_style_bg_opa(255, 0)
    cbox.set_style_radius(10, 0)

    mhdr = lv.label(cbox)
    mhdr.set_text("{} {}".format(MONTHS_FULL[(t[1] - 1) % 12], t[0]))
    mhdr.set_style_text_font(FONT_16, 0)
    mhdr.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    mhdr.align(lv.ALIGN.TOP_MID, 0, 5)

    for col_i, dname in enumerate(DAYS_SHORT):
        hcell = lv.obj(cbox)
        hcell.remove_style_all()
        hcell.set_size(26, 20)
        hcell.set_pos(4 + col_i * 26, 28)
        hl = lv.label(hcell)
        hl.set_text(dname)
        hl.set_style_text_font(FONT_14, 0)
        hl.set_style_text_color(lv.color_hex(0xFB7185 if col_i >= 5 else 0x94A3B8), 0)
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
        dl.set_style_text_font(FONT_16, 0)
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
    lbl_top_left.set_text("2/9 РЕТРО FLIP-ЧАСЫ" if RU_OK else "2/9 FLIP CLOCK")
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
        lbl.set_style_text_font(FONT_48, 0)
        lbl.set_style_text_color(lv.color_hex(0x00E5FF if i == 0 else 0xFFFFFF), 0)
        lbl.center()

    sub = lv.label(body)
    sub.set_text(
        "{}, {} {}  •  {} {} {}".format(
            DAYS_FULL[t[6] % 7], t[2], MONTHS_GEN[(t[1] - 1) % 12],
            IC_PIN, CITY_NAME[:11], fmt_temp(state["temp"])
        )
    )
    sub.set_style_text_font(FONT_16, 0)
    sub.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    sub.align(lv.ALIGN.BOTTOM_MID, 0, -14)

def build_v3():
    lbl_top_left.set_text("3/9 КАЛЕНДАРЬ ДНЯ" if RU_OK else "3/9 DAY CALENDAR")
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

    mh = lv.label(hdr)
    mh.set_text("{} {}".format(MONTHS_FULL[(t[1] - 1) % 12], t[0]))
    mh.set_style_text_font(FONT_16, 0)
    mh.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    mh.center()

    dl = lv.label(sheet)
    dl.set_text(str(t[2]))
    dl.set_style_text_font(FONT_48, 0)
    dl.set_style_text_color(lv.color_hex(0x0F172A), 0)
    dl.align(lv.ALIGN.CENTER, 0, 4)

    wl = lv.label(sheet)
    wl.set_text(DAYS_FULL[t[6] % 7].upper())
    wl.set_style_text_font(FONT_16, 0)
    wl.set_style_text_color(lv.color_hex(0x334155), 0)
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
    r_clk.set_style_text_font(FONT_36, 0)
    r_clk.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    r_clk.align(lv.ALIGN.TOP_MID, 0, 16)

    r_city = lv.label(rpanel)
    r_city.set_text("{} {}".format(IC_PIN, CITY_NAME[:11]))
    r_city.set_style_text_font(FONT_16, 0)
    r_city.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    r_city.align(lv.ALIGN.CENTER, 0, -6)

    r_tmp = lv.label(rpanel)
    r_tmp.set_text("{} {}".format(get_weather_icon(state["wcode"]), fmt_temp(state["temp"])).strip())
    r_tmp.set_style_text_font(FONT_24, 0)
    r_tmp.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    r_tmp.align(lv.ALIGN.CENTER, 0, 28)

    r_wnd = lv.label(rpanel)
    r_wnd.set_text(get_sync_badge_text())
    r_wnd.set_style_text_font(FONT_12, 0)
    r_wnd.set_style_text_color(lv.color_hex(0x10B981), 0)
    r_wnd.align(lv.ALIGN.BOTTOM_MID, 0, -12)

def build_v4():
    global sync_lbl_ref
    lbl_top_left.set_text("4/9 МЕТЕОСТАНЦИЯ" if RU_OK else "4/9 WEATHER PRO")
    t = get_dt()
    card = lv.obj(body)
    card.remove_style_all()
    card.set_size(304, 198)
    card.align(lv.ALIGN.CENTER, 0, 0)
    card.set_style_bg_color(lv.color_hex(0x101C33), 0)
    card.set_style_bg_opa(255, 0)
    card.set_style_radius(14, 0)

    c1 = lv.label(card)
    c1.set_text("{} {}   •   {:02d}:{:02d}".format(IC_PIN, CITY_NAME[:12], t[3], t[4]))
    c1.set_style_text_font(FONT_24, 0)
    c1.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    c1.set_pos(16, 12)

    c2 = lv.label(card)
    c2.set_text("{} {}  {}".format(
        get_weather_icon(state["wcode"]), fmt_temp(state["temp"]), get_weather_desc(state["wcode"])
    ).strip())
    c2.set_style_text_font(FONT_24, 0)
    c2.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    c2.set_pos(16, 56)

    c3 = lv.label(card)
    c3.set_text(
        ("Макс: {}   Мин: {}   Ветер: {:.1f} м/с" if RU_OK else "Max: {}   Min: {}   Wind: {:.1f} m/s").format(
            fmt_temp(state["tmax"]), fmt_temp(state["tmin"]), state["wind"]
        )
    )
    c3.set_style_text_font(FONT_14, 0)
    c3.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    c3.set_pos(16, 114)

    c4 = lv.label(card)
    c4.set_text(
        ("Метеостанция: {} (Обн #{})" if RU_OK else "Status: {} (Sync #{})").format(
            get_sync_badge_text(), state["sync_count"]
        )
    )
    c4.set_style_text_font(FONT_14, 0)
    c4.set_style_text_color(lv.color_hex(0x10B981), 0)
    c4.set_pos(16, 154)
    sync_lbl_ref = c4

def build_v5():
    lbl_top_left.set_text("5/9 ПЛАНЕР ДНЯ" if RU_OK else "5/9 DAILY PLANNER")
    t = get_dt()
    hdr = lv.label(body)
    hdr.set_text("{:02d}:{:02d}  •  {:02d}.{:02d}  •  {} {} {}".format(
        t[3], t[4], t[2], t[1], IC_PIN, CITY_NAME[:9], fmt_temp(state["temp"])
    ))
    hdr.set_style_text_font(FONT_16, 0)
    hdr.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    hdr.set_pos(12, 8)

    for i, note in enumerate(NOTES_LIST[:3]):
        row = lv.obj(body)
        row.remove_style_all()
        row.set_size(296, 48)
        row.set_pos(12, 42 + i * 54)
        row.set_style_bg_color(lv.color_hex(0x111E36), 0)
        row.set_style_bg_opa(255, 0)
        row.set_style_radius(10, 0)
        nl = lv.label(row)
        nl.set_text("{}. {}".format(i + 1, str(note)[:28]))
        nl.set_style_text_font(FONT_16, 0)
        nl.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        nl.align(lv.ALIGN.LEFT_MID, 14, 0)

def build_v6():
    lbl_top_left.set_text("6/9 МИРОВОЕ ВРЕМЯ" if RU_OK else "6/9 WORLD CLOCK")
    t_local = get_dt()
    utc_h = (t_local[3] - int(TZ_OFFSET // 3600)) % 24
    tok_h = (utc_h + 9) % 24

    zones = [
        ("{} {}".format(IC_PIN, CITY_NAME[:12]), t_local[3], t_local[4], 0x00E5FF),
        ("Лондон (UTC)" if RU_OK else "London / UTC", utc_h, t_local[4], 0x10B981),
        ("Токио (JST)" if RU_OK else "Tokyo (JST)", tok_h, t_local[4], 0xFBBF24)
    ]
    for i, (zname, zh, zm, col) in enumerate(zones):
        box = lv.obj(body)
        box.remove_style_all()
        box.set_size(296, 60)
        box.set_pos(12, 8 + i * 68)
        box.set_style_bg_color(lv.color_hex(0x111E36), 0)
        box.set_style_bg_opa(255, 0)
        box.set_style_radius(12, 0)

        zn = lv.label(box)
        zn.set_text(zname)
        zn.set_style_text_font(FONT_16, 0)
        zn.set_style_text_color(lv.color_hex(col), 0)
        zn.align(lv.ALIGN.LEFT_MID, 14, 0)

        zv = lv.label(box)
        zv.set_text("{:02d}:{:02d}".format(zh, zm))
        zv.set_style_text_font(FONT_32, 0)
        zv.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        zv.align(lv.ALIGN.RIGHT_MID, -14, 0)

def build_v7():
    lbl_top_left.set_text("7/9 ДО СОБЫТИЯ" if RU_OK else "7/9 COUNTDOWN")
    t = get_dt()
    card = lv.obj(body)
    card.remove_style_all()
    card.set_size(296, 196)
    card.align(lv.ALIGN.CENTER, 0, 0)
    card.set_style_bg_color(lv.color_hex(0x111E36), 0)
    card.set_style_bg_opa(255, 0)
    card.set_style_radius(14, 0)

    l1 = lv.label(card)
    l1.set_text(EVENT_TITLE.upper())
    l1.set_style_text_font(FONT_24, 0)
    l1.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    l1.align(lv.ALIGN.TOP_MID, 0, 18)

    l2 = lv.label(card)
    l2.set_text(EVENT_DAYS)
    l2.set_style_text_font(FONT_24, 0)
    l2.set_style_text_color(lv.color_hex(0x10B981), 0)
    l2.align(lv.ALIGN.CENTER, 0, 0)

    l3 = lv.label(card)
    l3.set_text("{:02d}:{:02d}  •  {} {} {}".format(t[3], t[4], IC_PIN, CITY_NAME[:10], fmt_temp(state["temp"])))
    l3.set_style_text_font(FONT_16, 0)
    l3.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    l3.align(lv.ALIGN.BOTTOM_MID, 0, -16)

def build_v8():
    global pomo_lbl_ref
    lbl_top_left.set_text("8/9 ПОМОДОРО" if RU_OK else "8/9 POMODORO")
    t = get_dt()
    mins = state["pomo_sec"] // 60
    secs = state["pomo_sec"] % 60

    pl = lv.label(body)
    pl.set_text("{:02d}:{:02d}".format(mins, secs))
    pl.set_style_text_font(FONT_48, 0)
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
    bl = lv.label(badge)
    bl.set_text("ФОКУС-СЕССИЯ 25 МИН" if RU_OK else "FOCUS 25 MIN ACTIVE")
    bl.set_style_text_font(FONT_16, 0)
    bl.set_style_text_color(lv.color_hex(0x10B981), 0)
    bl.center()

    cl = lv.label(body)
    cl.set_text("{:02d}:{:02d}  •  {} {} {}".format(t[3], t[4], IC_PIN, CITY_NAME[:10], fmt_temp(state["temp"])))
    cl.set_style_text_font(FONT_16, 0)
    cl.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    cl.align(lv.ALIGN.BOTTOM_MID, 0, -16)

def build_v9():
    lbl_top_left.set_text("9/9 НОЧНЫЕ ЧАСЫ" if RU_OK else "9/9 NIGHT CLOCK")
    t = get_dt()
    nc = lv.label(body)
    nc.set_text("{:02d}:{:02d}".format(t[3], t[4]))
    nc.set_style_text_font(FONT_48, 0)
    nc.set_style_text_color(lv.color_hex(0xFFB000), 0)
    nc.align(lv.ALIGN.CENTER, 0, -24)

    nd = lv.label(body)
    nd.set_text("{}, {} {} {}".format(DAYS_FULL[t[6] % 7], t[2], MONTHS_GEN[(t[1] - 1) % 12], t[0]))
    nd.set_style_text_font(FONT_16, 0)
    nd.set_style_text_color(lv.color_hex(0xF59E0B), 0)
    nd.align(lv.ALIGN.CENTER, 0, 28)

    nw = lv.label(body)
    nw.set_text("{} {}  •  {}  •  {}".format(
        IC_PIN, CITY_NAME[:10], fmt_temp(state["temp"]), get_sync_badge_text()
    ))
    nw.set_style_text_font(FONT_14, 0)
    nw.set_style_text_color(lv.color_hex(0xB45309), 0)
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
            "ru_fonts": RU_OK,
            "city": CITY_NAME,
            "station": WEATHER_STATION,
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
    lbl_top_right.set_text("ОБНОВЛЕНИЕ..." if RU_OK else "NET SYNCING...")
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
    try:
        import urequests
        if WEATHER_STATION == "met_no":
            url = "https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={:.4f}&lon={:.4f}".format(CITY_LAT, CITY_LON)
            r = urequests.get(url, headers={"User-Agent": "CYD2432-Meteo/1.0"})
            data = r.json()
            r.close()
            det = data["properties"]["timeseries"][0]["data"]["instant"]["details"]
            t_now = float(det.get("air_temperature", state["temp"]))
            state["temp"] = t_now
            state["tmax"] = round(t_now + 2.5, 1)
            state["tmin"] = round(t_now - 2.5, 1)
            state["wind"] = float(det.get("wind_speed", state["wind"]))
            state["hum"] = int(det.get("relative_humidity", state["hum"]))
            weather_updated = True
    except Exception as e:
        print("MET_NO_ERR:", e)

    if not weather_updated:
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
                    cw = data["current_weather"]
                    t_now = float(cw.get("temperature", state["temp"]))
                    state["temp"] = t_now
                    state["tmax"] = round(t_now + 3.0, 1)
                    state["tmin"] = round(t_now - 2.0, 1)
                    state["wind"] = float(cw.get("windspeed", state["wind"]))
                    state["wcode"] = int(cw.get("weathercode", state["wcode"]))
                    weather_updated = True
                    break
            except Exception as e:
                print("OPEN_METEO_ERR:", e)

    led_b.value(1)
    t_now = get_dt()
    state["last_sync_str"] = "{:02d}:{:02d}".format(t_now[3], t_now[4])
    state["sync_source"] = "WIFI" if weather_updated or state["ntp_applied"] else "USB"
    state["sync_count"] += 1
    state["next_sync_sec"] = 300
    state["wifi_synced"] = True
    render_current()

start_wifi_nonblocking()

def tick_cb(t):
    global current_idx
    state["ticks"] += 1
    t_now = get_dt()

    if state["wifi_connecting"] and wlan is not None:
        state["connect_sec"] += 1
        try:
            if wlan.isconnected():
                state["wifi_connecting"] = False
                state["wifi_ok"] = True
                state["wifi_err"] = False
                sync_ntp_and_weather()
            elif state["connect_sec"] >= 14:
                state["wifi_connecting"] = False
                state["wifi_ok"] = False
                state["wifi_err"] = True
                try:
                    wlan.disconnect()
                except Exception:
                    pass
                render_current()
        except Exception:
            state["wifi_connecting"] = False
            state["wifi_err"] = True

    if state["wifi_ok"]:
        if state["next_sync_sec"] > 0:
            state["next_sync_sec"] -= 1
        else:
            try:
                if wlan and wlan.isconnected():
                    sync_ntp_and_weather()
                else:
                    state["wifi_ok"] = False
                    start_wifi_nonblocking()
            except Exception:
                pass
    elif WIFI_SSID and not state["wifi_connecting"] and (state["ticks"] % 60 == 0):
        start_wifi_nonblocking()

    update_top_status_bar()

    if current_idx == 0 and sec_lbl_ref is not None:
        try:
            sec_lbl_ref.set_text(("{} :{:02d}с" if RU_OK else "{} :{:02d}s").format(DAYS_FULL[t_now[6] % 7][:9], t_now[5]))
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
    # ВАЖНО: block_count=189 строго соответствует размеру раздела `vfs` в таблице разделов ESP32 (0xBD000 / 4096 = 189)!
    fs = LittleFS(block_size=4096, block_count=189, disk_version=0x00020000)
    with fs.open("/boot.py", "w") as f:
        f.write(BOOT_PY)
    with fs.open("/config.txt", "wb") as f:
        f.write(DEFAULT_CFG_BYTES)

    fonts_dir = os.path.join(os.path.dirname(__file__), "fonts")
    for fname in ("ru_12.bin", "ru_14.bin", "ru_16.bin", "ru_24.bin"):
        fpath = os.path.join(fonts_dir, fname)
        with open(fpath, "rb") as rf:
            font_bytes = rf.read()
        with fs.open("/" + fname, "wb") as wf:
            wf.write(font_bytes)

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

    print(f"✅ Создан образ LittleFS v2: {out_path} ({trimmed_len} байт, последний блок: {last_used_block}, block_count=189)")


if __name__ == "__main__":
    main()
