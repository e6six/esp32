#!/usr/bin/env python3
"""
Генератор готового образа файловой системы LittleFS v2 (vfs_widgets.bin)
для прямой прошивки в раздел `vfs` (смещение 0x343000) платы ESP32-2432S028 / S024 (L1435-2.4).
Включает встроенные русские шрифты Montserrat + иконки FontAwesome (ru_12.bin, ru_14.bin, ru_16.bin, ru_24.bin),
поддержку районов Москвы (Бутово и др.) и Яндекс Погоды.
"""

import os
import json
from littlefs import LittleFS

BOOT_PY = """# boot.py - Fast boot for ESP32 CYD
import gc
import machine

# Гасим задний/передний RGB-светодиод (Active LOW: 1 = ВЫКЛ)
for _p in (4, 16, 17):
    try:
        machine.Pin(_p, machine.Pin.OUT, value=1)
    except Exception:
        pass

gc.collect()
"""

DEFAULT_CFG = {
    "cydVariant": "s024_perfect",
    "wifiSsid": "",
    "wifiPassword": "",
    "yandexApiKey": "",
    "cityRu": "Бутово",
    "cityEn": "Butovo",
    "latitude": 55.5520,
    "longitude": 37.5510,
    "timezoneOffset": 3,
    "selectedWidget": "v1_classic_cal",
    "notes": [
        "Утренняя разминка и кофе",
        "Проверить задачи на день",
        "Вечерняя прогулка в 19:00"
    ],
    "eventTitle": "ДО НОВОГО ГОДА",
    "eventDays": "73 ДНЯ",
    "tempC": 4,
    "tmaxC": 6,
    "tminC": 1,
    "windMs": 3.8,
    "humidity": 72,
    "wcode": 3,
    "descRu": "Пасмурно",
    "weatherSource": "Яндекс",
    "rtcTuple": [2026, 10, 20, 1, 14, 30, 0]
}

MAIN_PY = """# ============================================================================
# ESP32-2432S024 / S028 (L i 435-2 4) — 9 РУССКИХ ВИДЖЕТОВ + ЯНДЕКС ПОГОДА
# Полная русификация (Montserrat Cyrillic + FontAwesome Pin/Weather Icons)
# ============================================================================
import gc
import os
import sys
import select
import time
import json
import machine
import lvgl as lv
import lcd_bus
import ili9341
import task_handler

for _p in (4, 16, 17):
    try:
        machine.Pin(_p, machine.Pin.OUT, value=1)
    except Exception:
        pass

def set_rgb_led(r_on, g_on, b_on):
    try:
        machine.Pin(4, machine.Pin.OUT, value=0 if r_on else 1)
        machine.Pin(16, machine.Pin.OUT, value=0 if g_on else 1)
        machine.Pin(17, machine.Pin.OUT, value=0 if b_on else 1)
    except Exception:
        pass

def parse_cydcfg_bytes(raw_bytes):
    if not raw_bytes:
        return None
    idx = raw_bytes.find(b"CYDCFG1:")
    if idx < 0:
        return None
    payload = raw_bytes[idx + 8:]
    end = payload.find(b"\\x00")
    if end >= 0:
        payload = payload[:end]
    txt = payload.decode("utf-8", "ignore").strip()
    return json.loads(txt)

def load_user_config():
    cfg = {
        "cydVariant": "s024_perfect",
        "wifiSsid": "",
        "wifiPassword": "",
        "yandexApiKey": "",
        "cityRu": "Бутово",
        "cityEn": "Butovo",
        "latitude": 55.5520,
        "longitude": 37.5510,
        "timezoneOffset": 3,
        "selectedWidget": "v1_classic_cal",
        "notes": ["Утренняя разминка и кофе", "Проверить задачи на день", "Вечерняя прогулка в 19:00"],
        "eventTitle": "ДО НОВОГО ГОДА",
        "eventDays": "73 ДНЯ",
        "tempC": 4,
        "tmaxC": 6,
        "tminC": 1,
        "windMs": 3.8,
        "humidity": 72,
        "wcode": 3,
        "descRu": "Пасмурно",
        "weatherSource": "Яндекс"
    }
    try:
        with open("/config.txt", "rb") as f:
            parsed = parse_cydcfg_bytes(f.read())
            if parsed:
                cfg.update(parsed)
                return cfg
    except Exception as e:
        print("Config file read err:", e)
    return cfg

CFG = load_user_config()

rtc_Sync_str = "--:--"
try:
    rt = CFG.get("rtcTuple")
    if rt and len(rt) >= 7 and int(rt[0]) >= 2025:
        machine.RTC().datetime((int(rt[0]), int(rt[1]), int(rt[2]), int(rt[3]), int(rt[4]), int(rt[5]), int(rt[6]), 0))
        rtc_Sync_str = "{:02d}:{:02d}".format(int(rt[4]), int(rt[5]))
except Exception as e:
    print("RTC init err:", e)

CYD_VARIANT = str(CFG.get("cydVariant", "s024_perfect"))
WIFI_SSID = str(CFG.get("wifiSsid", ""))
WIFI_PASS = str(CFG.get("wifiPassword", ""))
YANDEX_API_KEY = str(CFG.get("yandexApiKey", ""))
CITY_RU = str(CFG.get("cityRu") or CFG.get("cityEn") or "Бутово")
CITY_NAME = str(CFG.get("cityEn", "Butovo"))
CITY_LAT = float(CFG.get("latitude", 55.5520))
CITY_LON = float(CFG.get("longitude", 37.5510))
TZ_OFFSET = int(float(CFG.get("timezoneOffset", 3)) * 3600)
START_WIDGET = str(CFG.get("selectedWidget", "v1_classic_cal"))
NOTES_LIST = list(CFG.get("notes", ["Утренняя разминка и кофе", "Проверить задачи на день", "Вечерняя прогулка в 19:00"]))
while len(NOTES_LIST) < 3:
    NOTES_LIST.append("Отличного дня!")

PROFILES = {
    "s024_perfect":  (0x60, False, 0x20),
    "s024_bgr_inv0": (0x60, True,  0x20),
    "s024_rgb_inv1": (0x60, False, 0x21),
    "s024_bgr_inv1": (0x60, True,  0x21),
}
rot_hex, use_bgr, inv_cmd = PROFILES.get(CYD_VARIANT, (0x60, False, 0x20))

for _bl_pin in (27, 21):
    try:
        machine.Pin(_bl_pin, machine.Pin.OUT, value=1)
    except Exception:
        pass

# Экран на своей выделенной шине SPI2 (host=1) — 0% мерцания
spi_bus = machine.SPI.Bus(host=1, mosi=13, miso=12, sck=14)
display_bus = lcd_bus.SPIBus(spi_bus=spi_bus, freq=24000000, dc=2, cs=15)

display = ili9341.ILI9341(
    data_bus=display_bus,
    display_width=320,
    display_height=240,
    backlight_pin=27,
    backlight_on_state=ili9341.STATE_HIGH,
    color_space=lv.COLOR_FORMAT.RGB565,
    color_byte_order=ili9341.BYTE_ORDER_BGR if use_bgr else ili9341.BYTE_ORDER_RGB,
    rgb565_byte_swap=1
)
display._ORIENTATION_TABLE = (rot_hex, 0x0, 0x0, 0x0)
display.set_rotation(lv.DISPLAY_ROTATION._0)
display.set_power(True)
display.init(1)
try:
    display.set_color_inversion(inv_cmd == 0x21)
except Exception:
    try:
        display_bus.tx_param(inv_cmd, None)
    except Exception:
        pass
display.set_backlight(100)
for _bl_pin in (27, 21):
    try:
        machine.Pin(_bl_pin, machine.Pin.OUT, value=1)
    except Exception:
        pass

# Регистрация файлового драйвера LVGL и загрузка русских шрифтов + иконок FontAwesome
_open_refs = []
try:
    import fs_driver
    fs_drv = lv.fs_drv_t()
    fs_driver.fs_register(fs_drv, 'S', cache_size=2048)
    _orig_open = fs_driver._fs_open_cb
    def _pinned_open_cb(drv, path, mode):
        r = _orig_open(drv, path, mode)
        _open_refs.append(r)
        return r
    fs_drv.open_cb = _pinned_open_cb
except Exception as e:
    print("FS driver err:", e)

def load_ru_font(path, fallback):
    try:
        gc.collect()
        f = lv.binfont_create(path)
        if f:
            try:
                f.fallback = fallback
            except Exception:
                pass
            return f
    except Exception as e:
        print("Font err:", path, e)
    return fallback

FONT_12 = load_ru_font("S:/ru_12.bin", lv.font_montserrat_12)
FONT_14 = load_ru_font("S:/ru_14.bin", lv.font_montserrat_14)
FONT_16 = load_ru_font("S:/ru_16.bin", lv.font_montserrat_16)
FONT_24 = load_ru_font("S:/ru_24.bin", lv.font_montserrat_24)
_open_refs.clear()
gc.collect()

# Иконки FontAwesome, встроенные прямо в ru_12..ru_24
ICON_PIN       = "\\uf3c5"  # 📍 Маркер локации (fa-map-marker-alt)
ICON_WIFI      = "\\uf1eb"  # 📶 Wi-Fi
ICON_SYNC      = "\\uf021"  # 🔄 Синхронизация
ICON_OK        = "\\uf00c"  # ✓ Галочка
ICON_WARN      = "\\uf071"  # ⚠ Внимание
ICON_SUN       = "\\uf185"  # ☀ Ясно
ICON_CLOUD_SUN = "\\uf6c4"  # ⛅ Малооблачно
ICON_CLOUD     = "\\uf0c2"  # ☁ Облачно / Пасмурно
ICON_RAIN      = "\\uf73d"  # 🌧 Дождь
ICON_SNOW      = "\\uf2dc"  # ❄ Снег
ICON_WIND      = "\\uf72e"  # 💨 Ветер
ICON_CLOCK     = "\\uf017"  # 🕒 Часы
ICON_CAL       = "\\uf073"  # 📅 Календарь

th = task_handler.TaskHandler()

state = {
    "temp": float(CFG.get("tempC", 4)),
    "tmax": float(CFG.get("tmaxC", 6)),
    "tmin": float(CFG.get("tminC", 1)),
    "wind": float(CFG.get("windMs", 3.8)),
    "hum": int(CFG.get("humidity", 72)),
    "wcode": int(CFG.get("wcode", 3)),
    "desc_ru": str(CFG.get("descRu", "Пасмурно")),
    "source": str(CFG.get("weatherSource", "Яндекс")),
    "wifi_ok": False,
    "wifi_connecting": bool(WIFI_SSID),
    "wifi_err": False,
    "ntp_applied": False,
    "last_sync_str": rtc_Sync_str,
    "sync_count": 0,
    "next_sync_sec": 300,
    "connect_sec": 0,
    "idx": 0,
    "pomo_sec": 25 * 60,
    "ticks": 0
}

WIDGET_KEYS = [
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

WIDGET_TITLES = [
    "1/9 КАЛЕНДАРЬ",
    "2/9 КРУПНЫЕ ЧАСЫ",
    "3/9 ЯНДЕКС ПОГОДА",
    "4/9 НЕДЕЛЯ И ПЛАНЫ",
    "5/9 НОЧНОЙ НЕОН",
    "6/9 РЕТРО ТЕРМИНАЛ",
    "7/9 ПОМОДОРО",
    "8/9 МИРОВОЕ ВРЕМЯ",
    "9/9 СОЛНЦЕ И ДЕНЬ"
]

if START_WIDGET in WIDGET_KEYS:
    state["idx"] = WIDGET_KEYS.index(START_WIDGET)

DAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
DAYS_SHORT_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MONTHS_RU = [
    "", "ЯНВАРЬ", "ФЕВРАЛЬ", "МАРТ", "АПРЕЛЬ", "МАЙ", "ИЮНЬ",
    "ИЮЛЬ", "АВГУСТ", "СЕНТЯБРЬ", "ОКТЯБРЬ", "НОЯБРЬ", "ДЕКАБРЬ"
]
MONTHS_GEN_RU = [
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря"
]

def wmo_to_ru_and_icon(wcode):
    if wcode == 0:
        return ("Ясно", ICON_SUN, 0xFBBF24)
    if wcode in (1, 2):
        return ("Малооблачно", ICON_CLOUD_SUN, 0x38BDF8)
    if wcode == 3:
        return ("Пасмурно", ICON_CLOUD, 0x94A3B8)
    if wcode in (45, 48):
        return ("Туман", ICON_CLOUD, 0x94A3B8)
    if 51 <= wcode <= 67 or 80 <= wcode <= 82:
        return ("Дождь", ICON_RAIN, 0x38BDF8)
    if 71 <= wcode <= 77 or 85 <= wcode <= 86:
        return ("Снег", ICON_SNOW, 0xE2E8F0)
    if wcode >= 95:
        return ("Гроза", ICON_WARN, 0xFBBF24)
    return ("Облачно", ICON_CLOUD_SUN, 0x38BDF8)

def is_leap(y):
    return (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)

def days_in_month(y, m):
    if m in (1, 3, 5, 7, 8, 10, 12):
        return 31
    if m in (4, 6, 9, 11):
        return 30
    return 29 if is_leap(y) else 28

def first_weekday_of_month(y, m):
    t = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]
    y_adj = y - (1 if m < 3 else 0)
    w = (y_adj + y_adj // 4 - y_adj // 100 + y_adj // 400 + t[m - 1] + 1) % 7
    return (w + 6) % 7

scr = lv.screen_active()
scr.set_style_bg_color(lv.color_hex(0x070B14), 0)
scr.set_style_bg_opa(lv.OPA.COVER, 0)

# Верхняя панель статуса 320x24
top = lv.obj(scr)
top.remove_style_all()
top.set_size(320, 24)
top.set_pos(0, 0)
top.set_style_bg_color(lv.color_hex(0x101C33), 0)
top.set_style_bg_opa(lv.OPA.COVER, 0)

lbl_top_left = lv.label(top)
lbl_top_left.set_text(WIDGET_TITLES[state["idx"]])
lbl_top_left.set_style_text_color(lv.color_hex(0x00E5FF), 0)
lbl_top_left.set_style_text_font(FONT_12, 0)
lbl_top_left.align(lv.ALIGN.LEFT_MID, 8, 0)

dot_wifi = lv.obj(top)
dot_wifi.remove_style_all()
dot_wifi.set_size(8, 8)
dot_wifi.set_style_radius(4, 0)
dot_wifi.set_style_bg_opa(lv.OPA.COVER, 0)
dot_wifi.align(lv.ALIGN.RIGHT_MID, -6, 0)

lbl_top_right = lv.label(top)
if WIFI_SSID:
    lbl_top_right.set_text(ICON_WIFI + " Wi-Fi...")
    lbl_top_right.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    dot_wifi.set_style_bg_color(lv.color_hex(0xFBBF24), 0)
else:
    lbl_top_right.set_text("{} • OK {}".format(CITY_RU, state["last_sync_str"]))
    lbl_top_right.set_style_text_color(lv.color_hex(0x10B981), 0)
    dot_wifi.set_style_bg_color(lv.color_hex(0x10B981), 0)
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
    return ("+{:.0f}°C" if v > 0 else "{:.0f}°C").format(v)

def get_sync_badge_text():
    if state["wifi_connecting"]:
        return "{} Поиск Wi-Fi ({}с)".format(ICON_WIFI, state["connect_sec"])
    if state["wifi_ok"]:
        return "{} Яндекс • {}".format(ICON_WIFI, state["last_sync_str"])
    return "{} Яндекс • {}".format(ICON_OK, state["last_sync_str"])

def update_top_status_bar():
    pulse_on = (state["ticks"] % 2 == 0)
    if state["wifi_connecting"]:
        lbl_top_right.set_text("{} Wi-Fi... {}с".format(ICON_WIFI, state["connect_sec"]))
        lbl_top_right.set_style_text_color(lv.color_hex(0xFBBF24), 0)
        dot_wifi.set_style_bg_color(lv.color_hex(0xFBBF24 if pulse_on else 0x78350F), 0)
    elif state["wifi_ok"]:
        rem_m = state["next_sync_sec"] // 60
        rem_s = state["next_sync_sec"] % 60
        lbl_top_right.set_text("{} WIFI OK • {} ({:d}:{:02d})".format(ICON_WIFI, state["last_sync_str"], rem_m, rem_s))
        lbl_top_right.set_style_text_color(lv.color_hex(0x10B981), 0)
        dot_wifi.set_style_bg_color(lv.color_hex(0x10B981 if pulse_on else 0x064E3B), 0)
    elif state["wifi_err"]:
        lbl_top_right.set_text("{} • USB {}".format(CITY_RU, state["last_sync_str"]))
        lbl_top_right.set_style_text_color(lv.color_hex(0xFBBF24), 0)
        dot_wifi.set_style_bg_color(lv.color_hex(0xEF4444 if pulse_on else 0x7F1D1D), 0)
    else:
        lbl_top_right.set_text("{} • OK {}".format(CITY_RU, state["last_sync_str"]))
        lbl_top_right.set_style_text_color(lv.color_hex(0x10B981), 0)
        dot_wifi.set_style_bg_color(lv.color_hex(0x10B981 if pulse_on else 0x064E3B), 0)

def make_card(parent, x, y, w, h, bg_hex, border_hex=0x1E293B, radius=10):
    c = lv.obj(parent)
    c.remove_style_all()
    c.set_pos(x, y)
    c.set_size(w, h)
    c.set_style_bg_color(lv.color_hex(bg_hex), 0)
    c.set_style_bg_opa(lv.OPA.COVER, 0)
    c.set_style_radius(radius, 0)
    if border_hex is not None:
        c.set_style_border_width(1, 0)
        c.set_style_border_color(lv.color_hex(border_hex), 0)
    return c

# Ссылки для плавного ежесекундного обновления без перерисовки экрана
clock_lbl_ref = None
sec_lbl_ref = None
sync_lbl_ref = None

# ============================================================================
# 1/9: КЛАССИЧЕСКИЙ КАЛЕНДАРЬ НА РУССКОМ + ЯНДЕКС ПОГОДА С ПИНОМ 📍
# ============================================================================
def build_v1():
    global clock_lbl_ref, sec_lbl_ref, sync_lbl_ref
    t = get_dt()
    year, month, mday, hh, mm, ss, wday = t[0], t[1], t[2], t[3], t[4], t[5], t[6]

    left = lv.obj(body)
    left.remove_style_all()
    left.set_pos(6, 2)
    left.set_size(108, 210)

    clock_lbl_ref = lv.label(left)
    clock_lbl_ref.set_text("{:02d}:{:02d}".format(hh, mm))
    clock_lbl_ref.set_style_text_font(lv.font_montserrat_40, 0)
    clock_lbl_ref.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    clock_lbl_ref.set_pos(2, 0)

    day_lbl = lv.label(left)
    day_lbl.set_text("{} • {:02d}с".format(DAYS_RU[wday % 7], ss))
    day_lbl.set_style_text_font(FONT_12, 0)
    day_lbl.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    day_lbl.set_pos(2, 43)
    sec_lbl_ref = day_lbl

    date_lbl = lv.label(left)
    date_lbl.set_text("{:02d}.{:02d}.{:04d}".format(mday, month, year))
    date_lbl.set_style_text_font(FONT_12, 0)
    date_lbl.set_style_text_color(lv.color_hex(0xCBD5E1), 0)
    date_lbl.set_pos(2, 60)

    # Карточка Яндекс Погоды (оформлена точь-в-точь как в предпросмотре на сайте)
    wcard = make_card(left, 0, 80, 108, 128, 0x0F172A, 0x1E293B, 10)

    # Красный пин 📍 + жёлтое название района/города
    pin_lbl = lv.label(wcard)
    pin_lbl.set_text(ICON_PIN)
    pin_lbl.set_style_text_font(FONT_14, 0)
    pin_lbl.set_style_text_color(lv.color_hex(0xFB7185), 0)
    pin_lbl.set_pos(8, 7)

    city_lbl = lv.label(wcard)
    city_lbl.set_text(CITY_RU)
    city_lbl.set_style_text_font(FONT_14, 0)
    city_lbl.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    city_lbl.set_pos(22, 7)

    # Крупная температура со знаком градуса +2°C
    t_lbl = lv.label(wcard)
    t_lbl.set_text(fmt_temp(state["temp"]))
    t_lbl.set_style_text_font(FONT_24, 0)
    t_lbl.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    t_lbl.set_pos(8, 28)

    # Иконка погоды и описание на русском ("☁ Пасмурно")
    desc_ru, w_icon, w_col = wmo_to_ru_and_icon(state["wcode"])
    if state.get("desc_ru"):
        desc_ru = state["desc_ru"]
    desc_lbl = lv.label(wcard)
    desc_lbl.set_text("{} {}".format(w_icon, desc_ru))
    desc_lbl.set_style_text_font(FONT_12, 0)
    desc_lbl.set_style_text_color(lv.color_hex(w_col), 0)
    desc_lbl.set_pos(8, 58)

    # Ветер на русском ("Ветер 5.8 м/с")
    w_lbl = lv.label(wcard)
    w_lbl.set_text("Ветер {:.1f} м/с".format(state["wind"]))
    w_lbl.set_style_text_font(FONT_12, 0)
    w_lbl.set_style_text_color(lv.color_hex(0x34D399), 0)
    w_lbl.set_pos(8, 78)

    # Статус синхронизации
    sync_lbl = lv.label(wcard)
    sync_lbl.set_text(get_sync_badge_text())
    sync_lbl.set_style_text_font(FONT_12, 0)
    sync_lbl.set_style_text_color(lv.color_hex(0x10B981 if state["wifi_ok"] else 0x64748B), 0)
    sync_lbl.set_pos(8, 100)
    sync_lbl_ref = sync_lbl

    # Правая карточка: Календарь на русском (196x204)
    cal = make_card(body, 118, 6, 196, 204, 0x0B1324, 0x1E293B, 10)

    m_title = lv.label(cal)
    m_title.set_text("{} {}".format(MONTHS_RU[month], year))
    m_title.set_style_text_font(FONT_16, 0)
    m_title.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    m_title.align(lv.ALIGN.TOP_MID, 0, 6)

    col_w = 26
    row_h = 25
    start_x = 7
    header_y = 28
    grid_y = 47

    for i, dname in enumerate(DAYS_SHORT_RU):
        dl = lv.label(cal)
        dl.set_text(dname)
        dl.set_style_text_font(FONT_12, 0)
        dl.set_style_text_color(lv.color_hex(0xFB7185 if i >= 5 else 0x94A3B8), 0)
        dl.set_width(col_w)
        dl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        dl.set_pos(start_x + i * col_w, header_y)

    first_w = first_weekday_of_month(year, month)
    total_d = days_in_month(year, month)

    for d in range(1, total_d + 1):
        idx_cell = first_w + (d - 1)
        col = idx_cell % 7
        row = idx_cell // 7
        cx = start_x + col * col_w
        cy = grid_y + row * row_h

        if d == mday:
            hl = lv.obj(cal)
            hl.remove_style_all()
            hl.set_pos(cx + 1, cy - 2)
            hl.set_size(24, 21)
            hl.set_style_bg_color(lv.color_hex(0x00E5FF), 0)
            hl.set_style_bg_opa(lv.OPA.COVER, 0)
            hl.set_style_radius(6, 0)

        nl = lv.label(cal)
        nl.set_text(str(d))
        nl.set_style_text_font(FONT_16, 0)
        if d == mday:
            nl.set_style_text_color(lv.color_hex(0x070B14), 0)
        elif col >= 5:
            nl.set_style_text_color(lv.color_hex(0xFDA4AF), 0)
        else:
            nl.set_style_text_color(lv.color_hex(0xF1F5F9), 0)
        nl.set_width(col_w)
        nl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        nl.set_pos(cx, cy)

# ============================================================================
# 2/9: КРУПНЫЕ ЧАСЫ НА РУССКОМ + ЯНДЕКС ПОГОДА
# ============================================================================
def build_v2():
    global clock_lbl_ref, sec_lbl_ref, sync_lbl_ref
    t = get_dt()
    card = make_card(body, 10, 8, 300, 114, 0x0F172A, 0x00E5FF, 14)

    clock_lbl_ref = lv.label(card)
    clock_lbl_ref.set_text("{:02d}:{:02d}".format(t[3], t[4]))
    clock_lbl_ref.set_style_text_font(lv.font_montserrat_48, 0)
    clock_lbl_ref.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    clock_lbl_ref.align(lv.ALIGN.CENTER, -24, -12)

    sec_lbl = lv.label(card)
    sec_lbl.set_text(":{:02d}".format(t[5]))
    sec_lbl.set_style_text_font(lv.font_montserrat_28, 0)
    sec_lbl.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    sec_lbl.align(lv.ALIGN.CENTER, 76, -6)
    sec_lbl_ref = sec_lbl

    sub = lv.label(card)
    sub.set_text("{}, {:02d} {}".format(DAYS_RU[t[6] % 7], t[2], MONTHS_GEN_RU[t[1]]))
    sub.set_style_text_font(FONT_16, 0)
    sub.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    sub.align(lv.ALIGN.BOTTOM_MID, 0, -10)

    bot = make_card(body, 10, 130, 300, 78, 0x111C35, 0x1E293B, 12)
    pin_l = lv.label(bot)
    pin_l.set_text(ICON_PIN)
    pin_l.set_style_text_font(FONT_16, 0)
    pin_l.set_style_text_color(lv.color_hex(0xFB7185), 0)
    pin_l.set_pos(12, 10)

    city_l = lv.label(bot)
    city_l.set_text("{}  •  {}".format(CITY_RU, fmt_temp(state["temp"])))
    city_l.set_style_text_font(FONT_16, 0)
    city_l.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    city_l.set_pos(30, 10)

    desc_ru, w_icon, _ = wmo_to_ru_and_icon(state["wcode"])
    if state.get("desc_ru"):
        desc_ru = state["desc_ru"]
    w_l = lv.label(bot)
    w_l.set_text("{} {}  •  Ветер {:.1f} м/с".format(w_icon, desc_ru, state["wind"]))
    w_l.set_style_text_font(FONT_14, 0)
    w_l.set_style_text_color(lv.color_hex(0x34D399), 0)
    w_l.set_pos(12, 34)

    sync_l = lv.label(bot)
    sync_l.set_text(get_sync_badge_text())
    sync_l.set_style_text_font(FONT_12, 0)
    sync_l.set_style_text_color(lv.color_hex(0x38BDF8), 0)
    sync_l.set_pos(12, 55)
    sync_lbl_ref = sync_l

# ============================================================================
# 3/9: МЕТЕОСТАНЦИЯ ЯНДЕКС ПОГОДА (РАЙОН МОСКВЫ / БУТОВО)
# ============================================================================
def build_v3():
    global clock_lbl_ref, sync_lbl_ref
    t = get_dt()
    card = make_card(body, 8, 8, 304, 200, 0x0F172A, 0x0284C7, 12)

    pin_l = lv.label(card)
    pin_l.set_text(ICON_PIN)
    pin_l.set_style_text_font(FONT_16, 0)
    pin_l.set_style_text_color(lv.color_hex(0xFB7185), 0)
    pin_l.set_pos(14, 10)

    hdr = lv.label(card)
    hdr.set_text("{}  •  {:02d}:{:02d}".format(CITY_RU, t[3], t[4]))
    hdr.set_style_text_font(FONT_16, 0)
    hdr.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    hdr.set_pos(32, 10)

    big_t = lv.label(card)
    big_t.set_text(fmt_temp(state["temp"]))
    big_t.set_style_text_font(FONT_24, 0)
    big_t.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    big_t.set_pos(14, 42)

    desc_ru, w_icon, w_col = wmo_to_ru_and_icon(state["wcode"])
    if state.get("desc_ru"):
        desc_ru = state["desc_ru"]
    cond = lv.label(card)
    cond.set_text("{} {}".format(w_icon, desc_ru))
    cond.set_style_text_font(FONT_16, 0)
    cond.set_style_text_color(lv.color_hex(w_col), 0)
    cond.set_pos(115, 48)

    d1 = lv.label(card)
    d1.set_text("Макс: {}   Мин: {}   Влажн: {}%".format(
        fmt_temp(state["tmax"]), fmt_temp(state["tmin"]), state["hum"]))
    d1.set_style_text_font(FONT_14, 0)
    d1.set_style_text_color(lv.color_hex(0xE2E8F0), 0)
    d1.set_pos(14, 92)

    d2 = lv.label(card)
    d2.set_text("{} Ветер: {:.1f} м/с   Коорд: {:.2f}, {:.2f}".format(
        ICON_WIND, state["wind"], CITY_LAT, CITY_LON))
    d2.set_style_text_font(FONT_14, 0)
    d2.set_style_text_color(lv.color_hex(0x34D399), 0)
    d2.set_pos(14, 122)

    d3 = lv.label(card)
    d3.set_text("Источник: {} (Обн #{})".format( get_sync_badge_text(), state["sync_count"] ))
    d3.set_style_text_font(FONT_12, 0)
    d3.set_style_text_color(lv.color_hex(0x38BDF8), 0)
    d3.set_pos(14, 162)
    sync_lbl_ref = d3

# ============================================================================
# 4/9: НЕДЕЛЯ И ПЛАНЫ НА ДЕНЬ
# ============================================================================
def build_v4():
    global clock_lbl_ref
    t = get_dt()
    wday = t[6] % 7

    for i in range(7):
        box = make_card(body, 8 + i * 44, 6, 40, 34, 0x00E5FF if i == wday else 0x111C35, None, 6)
        l1 = lv.label(box)
        l1.set_text(DAYS_SHORT_RU[i])
        l1.set_style_text_font(FONT_14, 0)
        l1.set_style_text_color(lv.color_hex(0x070B14 if i == wday else 0xE2E8F0), 0)
        l1.center()

    info = lv.label(body)
    info.set_text("{:02d}:{:02d}  •  {:02d}.{:02d}  •  {} {} {}".format(
        t[3], t[4], t[2], t[1], ICON_PIN, CITY_RU, fmt_temp(state["temp"])))
    info.set_style_text_font(FONT_14, 0)
    info.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    info.set_pos(10, 48)

    for idx_n in range(3):
        nc = make_card(body, 8, 74 + idx_n * 44, 304, 38, 0x0F172A, 0x1E293B, 8)
        nl = lv.label(nc)
        nl.set_text("{}. {}".format(idx_n + 1, NOTES_LIST[idx_n][:28]))
        nl.set_style_text_font(FONT_14, 0)
        nl.set_style_text_color(lv.color_hex(0xF8FAFC), 0)
        nl.align(lv.ALIGN.LEFT_MID, 10, 0)

# ============================================================================
# 5/9: НОЧНОЙ НЕОНОВЫЙ БУДИЛЬНИК
# ============================================================================
def build_v5():
    global clock_lbl_ref
    t = get_dt()
    frame = make_card(body, 10, 10, 300, 196, 0x050811, 0x00E5FF, 16)
    frame.set_style_border_width(2, 0)

    clock_lbl_ref = lv.label(frame)
    clock_lbl_ref.set_text("{:02d}:{:02d}".format(t[3], t[4]))
    clock_lbl_ref.set_style_text_font(lv.font_montserrat_48, 0)
    clock_lbl_ref.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    clock_lbl_ref.align(lv.ALIGN.CENTER, 0, -28)

    dl = lv.label(frame)
    dl.set_text("{}, {:02d} {}".format(DAYS_RU[t[6] % 7].upper(), t[2], MONTHS_RU[t[1]]))
    dl.set_style_text_font(FONT_16, 0)
    dl.set_style_text_color(lv.color_hex(0x38BDF8), 0)
    dl.align(lv.ALIGN.CENTER, 0, 22)

    wl = lv.label(frame)
    wl.set_text("{} {}  •  {}  •  {:.1f} м/с".format(ICON_PIN, CITY_RU, fmt_temp(state["temp"]), state["wind"]))
    wl.set_style_text_font(FONT_14, 0)
    wl.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    wl.align(lv.ALIGN.BOTTOM_MID, 0, -14)

# ============================================================================
# 6/9: РЕТРО ТЕРМИНАЛ CASIO / PIP-BOY НА РУССКОМ
# ============================================================================
def build_v6():
    global clock_lbl_ref
    t = get_dt()
    term = make_card(body, 8, 8, 304, 200, 0x041208, 0x10B981, 8)
    term.set_style_border_width(2, 0)

    hdr = lv.label(term)
    hdr.set_text("CASIO CYD-2432 // ЯНДЕКС РАДАР")
    hdr.set_style_text_font(FONT_12, 0)
    hdr.set_style_text_color(lv.color_hex(0x10B981), 0)
    hdr.set_pos(12, 10)

    clock_lbl_ref = lv.label(term)
    clock_lbl_ref.set_text("{:02d}:{:02d}".format(t[3], t[4]))
    clock_lbl_ref.set_style_text_font(lv.font_montserrat_44, 0)
    clock_lbl_ref.set_style_text_color(lv.color_hex(0x34D399), 0)
    clock_lbl_ref.set_pos(12, 32)

    l1 = lv.label(term)
    l1.set_text("ДАТА: {:02d}.{:02d}.{:04d} ({})".format(t[2], t[1], t[0], DAYS_SHORT_RU[t[6] % 7]))
    l1.set_style_text_font(FONT_14, 0)
    l1.set_style_text_color(lv.color_hex(0x10B981), 0)
    l1.set_pos(12, 92)

    l2 = lv.label(term)
    l2.set_text("ЛОКАЦИЯ: {}  •  {}".format(CITY_RU.upper(), fmt_temp(state["temp"])))
    l2.set_style_text_font(FONT_14, 0)
    l2.set_style_text_color(lv.color_hex(0xA7F3D0), 0)
    l2.set_pos(12, 118)

    l3 = lv.label(term)
    l3.set_text("ВЕТЕР: {:.1f} М/С  •  {}".format(state["wind"], get_sync_badge_text()))
    l3.set_style_text_font(FONT_12, 0)
    l3.set_style_text_color(lv.color_hex(0x34D399), 0)
    l3.set_pos(12, 148)

# ============================================================================
# 7/9: ТАЙМЕР ПОМОДОРО + ЧАСЫ И ПОГОДА
# ============================================================================
def build_v7():
    global clock_lbl_ref
    t = get_dt()
    card = make_card(body, 10, 8, 300, 200, 0x131C31, 0xF43F5E, 14)

    title = lv.label(card)
    title.set_text("ФОКУС-ТАЙМЕР ПОМОДОРО")
    title.set_style_text_font(FONT_14, 0)
    title.set_style_text_color(lv.color_hex(0xFB7185), 0)
    title.align(lv.ALIGN.TOP_MID, 0, 12)

    pm = state["pomo_sec"] // 60
    ps = state["pomo_sec"] % 60
    pl = lv.label(card)
    pl.set_text("{:02d}:{:02d}".format(pm, ps))
    pl.set_style_text_font(lv.font_montserrat_48, 0)
    pl.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    pl.align(lv.ALIGN.CENTER, 0, -6)
    clock_lbl_ref = pl

    sub = lv.label(card)
    sub.set_text("Время {:02d}:{:02d}  •  {} {} {}".format(t[3], t[4], ICON_PIN, CITY_RU, fmt_temp(state["temp"])))
    sub.set_style_text_font(FONT_14, 0)
    sub.set_style_text_color(lv.color_hex(0x38BDF8), 0)
    sub.align(lv.ALIGN.BOTTOM_MID, 0, -14)

# ============================================================================
# 8/9: МИРОВОЕ ВРЕМЯ (4 ГОРОДА НА РУССКОМ)
# ============================================================================
def build_v8():
    t = get_dt()
    utc_h = (t[3] - int(TZ_OFFSET // 3600)) % 24
    mm = t[4]
    zones = [
        (ICON_PIN + " " + CITY_RU, t[3], 0x00E5FF),
        ("Лондон (UTC+0)", utc_h, 0xE2E8F0),
        ("Токио (UTC+9)", (utc_h + 9) % 24, 0xFBBF24),
        ("Нью-Йорк (UTC-5)", (utc_h - 5) % 24, 0x34D399)
    ]
    for i, (zname, zh, zcol) in enumerate(zones):
        row = make_card(body, 8, 8 + i * 50, 304, 44, 0x0F172A, 0x1E293B, 8)
        nl = lv.label(row)
        nl.set_text(zname)
        nl.set_style_text_font(FONT_16, 0)
        nl.set_style_text_color(lv.color_hex(zcol), 0)
        nl.align(lv.ALIGN.LEFT_MID, 12, 0)

        tl = lv.label(row)
        tl.set_text("{:02d}:{:02d}".format(zh, mm))
        tl.set_style_text_font(lv.font_montserrat_24, 0)
        tl.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        tl.align(lv.ALIGN.RIGHT_MID, -12, 0)

# ============================================================================
# 9/9: ВОСХОД, ЗАКАТ И СВЕТОВОЙ ДЕНЬ
# ============================================================================
def build_v9():
    global clock_lbl_ref
    t = get_dt()
    card = make_card(body, 10, 8, 300, 200, 0x0F172A, 0xFBBF24, 14)

    hdr = lv.label(card)
    hdr.set_text("{} СВЕТОВОЙ ДЕНЬ И ПОГОДА".format(ICON_SUN))
    hdr.set_style_text_font(FONT_14, 0)
    hdr.set_style_text_color(lv.color_hex(0xFBBF24), 0)
    hdr.align(lv.ALIGN.TOP_MID, 0, 12)

    clock_lbl_ref = lv.label(card)
    clock_lbl_ref.set_text("{:02d}:{:02d}".format(t[3], t[4]))
    clock_lbl_ref.set_style_text_font(lv.font_montserrat_40, 0)
    clock_lbl_ref.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    clock_lbl_ref.align(lv.ALIGN.CENTER, 0, -24)

    sun = lv.label(card)
    sun.set_text("Восход: 07:12   •   Закат: 17:48")
    sun.set_style_text_font(FONT_14, 0)
    sun.set_style_text_color(lv.color_hex(0x38BDF8), 0)
    sun.align(lv.ALIGN.CENTER, 0, 16)

    w = lv.label(card)
    w.set_text("{} {}  •  {}  •  Ветер {:.1f} м/с".format(ICON_PIN, CITY_RU, fmt_temp(state["temp"]), state["wind"]))
    w.set_style_text_font(FONT_14, 0)
    w.set_style_text_color(lv.color_hex(0x34D399), 0)
    w.align(lv.ALIGN.BOTTOM_MID, 0, -14)

BUILDERS = [
    build_v1, build_v2, build_v3, build_v4, build_v5,
    build_v6, build_v7, build_v8, build_v9
]

def render_active():
    global clock_lbl_ref, sec_lbl_ref, sync_lbl_ref
    clock_lbl_ref = None
    sec_lbl_ref = None
    sync_lbl_ref = None
    idx = state["idx"] % len(BUILDERS)
    lbl_top_left.set_text(WIDGET_TITLES[idx])
    update_top_status_bar()
    body.clean()
    gc.collect()
    BUILDERS[idx]()
    gc.collect()

render_active()

# ============================================================================
# МГНОВЕННОЕ ПЕРЕКЛЮЧЕНИЕ И ОБНОВЛЕНИЕ ЯНДЕКС ПОГОДЫ ПО USB
# ============================================================================
poll_usb = select.poll()
poll_usb.register(sys.stdin, select.POLLIN)
usb_buf = ""

def check_usb_commands():
    global usb_buf
    try:
        while poll_usb.poll(0):
            ch = sys.stdin.read(1)
            if not ch:
                break
            if ch in ("\\n", "\\r"):
                cmd = usb_buf.strip()
                usb_buf = ""
                if cmd.startswith("SET:"):
                    wkey = cmd[4:].strip()
                    if wkey in WIDGET_KEYS:
                        state["idx"] = WIDGET_KEYS.index(wkey)
                        render_active()
                elif cmd == "NEXT":
                    state["idx"] = (state["idx"] + 1) % len(BUILDERS)
                    render_active()
                elif cmd == "PREV":
                    state["idx"] = (state["idx"] - 1) % len(BUILDERS)
                    render_active()
                elif cmd.startswith("WUPD:"):
                    # Формат: WUPD:temp|tmax|tmin|wind|wcode|desc_ru|hh:mm
                    parts = cmd[5:].split("|")
                    if len(parts) >= 7:
                        state["temp"] = float(parts[0])
                        state["tmax"] = float(parts[1])
                        state["tmin"] = float(parts[2])
                        state["wind"] = float(parts[3])
                        state["wcode"] = int(parts[4])
                        state["desc_ru"] = parts[5]
                        state["last_sync_str"] = parts[6]
                        state["sync_count"] += 1
                        render_active()
            else:
                if len(usb_buf) < 160:
                    usb_buf += ch
    except Exception:
        pass

# ============================================================================
# ФОНОВЫЙ WI-FI + АВТООБНОВЛЕНИЕ ПОГОДЫ РАЙОНА КАЖДЫЕ 5 МИНУТ
# ============================================================================
wlan = None
def start_wifi_nonblocking():
    global wlan
    if not WIFI_SSID:
        state["wifi_connecting"] = False
        return
    try:
        import network
        wlan = network.WLAN(network.STA_IF)
        wlan.active(False)
        time.sleep_ms(40)
        wlan.active(True)
        wlan.connect(WIFI_SSID, WIFI_PASS)
        state["wifi_connecting"] = True
        state["wifi_err"] = False
        state["connect_sec"] = 0
        update_top_status_bar()
    except Exception as e:
        print("WiFi init err:", e)
        state["wifi_connecting"] = False
        state["wifi_err"] = True
        update_top_status_bar()

def sync_ntp_and_weather():
    lbl_top_right.set_text(ICON_SYNC + " ОБНОВЛЕНИЕ...")
    lbl_top_right.set_style_text_color(lv.color_hex(0x00E5FF), 0)
    dot_wifi.set_style_bg_color(lv.color_hex(0x00E5FF), 0)
    set_rgb_led(False, False, True)

    if not state["ntp_applied"]:
        try:
            import ntptime
            ntptime.timeout = 2
            ntptime.settime()
            state["ntp_applied"] = True
        except Exception as e:
            print("NTP err:", e)

    weather_updated = False
    # 1. Если задан ключ Яндекс Погоды — опрашиваем напрямую api.weather.yandex.ru
    if YANDEX_API_KEY and len(YANDEX_API_KEY) > 8:
        try:
            import urequests
            yurl = "https://api.weather.yandex.ru/v2/informers?lat={}&lon={}&lang=ru_RU".format(CITY_LAT, CITY_LON)
            r = urequests.get(yurl, headers={"X-Yandex-Weather-Key": YANDEX_API_KEY}, timeout=4)
            d = r.json()
            r.close()
            if "fact" in d:
                state["temp"] = float(d["fact"].get("temp", state["temp"]))
                state["wind"] = float(d["fact"].get("wind_speed", state["wind"]))
                state["hum"] = int(d["fact"].get("humidity", state["hum"]))
                weather_updated = True
        except Exception as e:
            print("Yandex API err:", e)

    # 2. Гиперлокальный прогноз по координатам района (Бутово 55.5520, 37.5510 и др.) с ветром в м/с
    if not weather_updated:
        for proto in ("http", "https"):
            try:
                import urequests
                url = "{}://api.open-meteo.com/v1/forecast?latitude={}&longitude={}&current_weather=true&windspeed_unit=ms".format(proto, CITY_LAT, CITY_LON)
                r = urequests.get(url, timeout=4)
                d = r.json()
                r.close()
                if "current_weather" in d:
                    cw = d["current_weather"]
                    state["temp"] = float(cw.get("temperature", state["temp"]))
                    state["wind"] = float(cw.get("windspeed", state["wind"]))
                    state["wcode"] = int(cw.get("weathercode", state["wcode"]))
                    desc_ru, _, _ = wmo_to_ru_and_icon(state["wcode"])
                    state["desc_ru"] = desc_ru
                    state["tmax"] = state["temp"] + 2
                    state["tmin"] = state["temp"] - 2
                    weather_updated = True
                    break
            except Exception as e:
                print("Weather err:", e)

    set_rgb_led(False, False, False)
    t = get_dt()
    state["last_sync_str"] = "{:02d}:{:02d}".format(t[3], t[4])
    state["sync_count"] += 1
    state["next_sync_sec"] = 300
    render_active()

start_wifi_nonblocking()
last_sec = time.ticks_ms()
last_minute_shown = get_dt()[4]

while True:
    check_usb_commands()
    now_ms = time.ticks_ms()

    if time.ticks_diff(now_ms, last_sec) >= 1000:
        last_sec = now_ms
        state["ticks"] += 1

        if state["pomo_sec"] > 0:
            state["pomo_sec"] -= 1

        if wlan and not state["wifi_ok"]:
            try:
                if wlan.isconnected():
                    state["wifi_ok"] = True
                    state["wifi_connecting"] = False
                    state["wifi_err"] = False
                    sync_ntp_and_weather()
                elif state["wifi_connecting"]:
                    state["connect_sec"] += 1
                    if state["connect_sec"] > 22:
                        state["wifi_connecting"] = False
                        state["wifi_err"] = True
            except Exception:
                pass
        elif state["wifi_ok"] and wlan:
            try:
                if not wlan.isconnected():
                    state["wifi_ok"] = False
                    state["wifi_connecting"] = True
                    state["connect_sec"] = 0
                else:
                    if state["next_sync_sec"] > 0:
                        state["next_sync_sec"] -= 1
                    else:
                        sync_ntp_and_weather()
            except Exception:
                pass
        elif state["wifi_err"] and WIFI_SSID and (state["ticks"] % 60 == 0):
            start_wifi_nonblocking()

        update_top_status_bar()
        t = get_dt()

        if sec_lbl_ref is not None:
            try:
                if state["idx"] == 0:
                    sec_lbl_ref.set_text("{} • {:02d}с".format(DAYS_RU[t[6] % 7], t[5]))
                elif state["idx"] == 1:
                    sec_lbl_ref.set_text(":{:02d}".format(t[5]))
            except Exception:
                pass

        if sync_lbl_ref is not None:
            try:
                sync_lbl_ref.set_text(get_sync_badge_text())
                sync_lbl_ref.set_style_text_color(
                    lv.color_hex(0x10B981 if state["wifi_ok"] else 0x38BDF8), 0
                )
            except Exception:
                pass

        if t[4] != last_minute_shown:
            last_minute_shown = t[4]
            if clock_lbl_ref is not None and state["idx"] != 6:
                try:
                    clock_lbl_ref.set_text("{:02d}:{:02d}".format(t[3], t[4]))
                except Exception:
                    render_active()
            else:
                render_active()

        if state["idx"] == 6 and clock_lbl_ref is not None:
            pm = state["pomo_sec"] // 60
            ps = state["pomo_sec"] % 60
            try:
                clock_lbl_ref.set_text("{:02d}:{:02d}".format(pm, ps))
            except Exception:
                pass

    time.sleep_ms(20)
"""


def build():
    # Раздел vfs имеет размер 0xBD000 (160 блоков по 4096 байт)
    fs = LittleFS(block_size=4096, block_count=160, disk_version=0x00020000)

    with fs.open("/boot.py", "w") as f:
        f.write(BOOT_PY + "# 12\n")
    fs.unmount()
    fs.mount()

    # Записываем резервированный 2048-байтный файл /config.txt с меткой CYDCFG1: в блок 2
    cfg_raw = ("CYDCFG1:" + json.dumps(DEFAULT_CFG, ensure_ascii=False) + "\x00").encode("utf-8")
    cfg_padded = cfg_raw + b" " * (2048 - len(cfg_raw))
    with fs.open("/config.txt", "wb") as f:
        f.write(cfg_padded)

    # Записываем русские шрифты + иконки FontAwesome в корень LittleFS (блоки 3..14)
    fonts_dir = os.path.join(os.path.dirname(__file__), "fonts")
    for fname in ("ru_12.bin", "ru_14.bin", "ru_16.bin", "ru_24.bin"):
        fpath = os.path.join(fonts_dir, fname)
        with open(fpath, "rb") as rf:
            fdata = rf.read()
        with fs.open("/" + fname, "wb") as wf:
            wf.write(fdata)

    with fs.open("/main.py", "w") as f:
        f.write(MAIN_PY)

    out_dir = os.path.join(os.path.dirname(__file__), "..", "public", "firmware")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "vfs_widgets.bin")

    raw_img = bytes(fs.context.buffer)
    idx = raw_img.find(b"CYDCFG1:")
    print(f"📍 Метка CYDCFG1: внутри vfs_widgets.bin по смещению {idx} (блок {idx // 4096}, смещение в блоке {idx % 4096})")

    last_used_block = 0
    for b in range(160):
        chunk = raw_img[b * 4096 : (b + 1) * 4096]
        if any(x != 0xFF for x in chunk):
            last_used_block = b

    trimmed = raw_img[: (last_used_block + 2) * 4096]
    with open(out_path, "wb") as f:
        f.write(trimmed)

    print(f"✅ Создан образ LittleFS v2: {out_path} ({len(trimmed)} байт, последний блок: {last_used_block})")


if __name__ == "__main__":
    build()
