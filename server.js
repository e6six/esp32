const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const os = require('os');

const PORT = process.env.PORT || 3000;
const HOST = '0.0.0.0';

const DATA_DIR = path.join(__dirname, 'data');
const CONFIG_PATH = path.join(DATA_DIR, 'config.json');
const PUBLIC_DIR = path.join(__dirname, 'public');

if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

// Районы Москвы и реальные бесплатные метеостанции (без платных API-ключей)
const CITIES_DB = {
  'Москва • Бутово': { shortRu: 'Бутово', en: 'Butovo', group: 'moscow', lat: 55.5520, lon: 37.5510, tz: 3 },
  'Москва • Южное Бутово': { shortRu: 'Ю. Бутово', en: 'Yuzhnoye Butovo', group: 'moscow', lat: 55.5385, lon: 37.5336, tz: 3 },
  'Москва • Северное Бутово': { shortRu: 'Сев. Бутово', en: 'Severnoye Butovo', group: 'moscow', lat: 55.5719, lon: 37.5714, tz: 3 },
  'Метеостанция Внуково (UUWW — у Бутово)': { shortRu: 'Внуково', en: 'Vnukovo UUWW', group: 'moscow', lat: 55.5915, lon: 37.2615, tz: 3 },
  'Метеообсерватория МГУ (ЮЗАО)': { shortRu: 'МГУ ЮЗАО', en: 'MSU Moscow', group: 'moscow', lat: 55.7072, lon: 37.5228, tz: 3 },
  'Метеостанция Домодедово (UUDD — Юг)': { shortRu: 'Домодедово', en: 'Domodedovo UUDD', group: 'moscow', lat: 55.4088, lon: 37.9063, tz: 3 },
  'Москва': { shortRu: 'Москва', en: 'Moscow', group: 'moscow', lat: 55.7558, lon: 37.6173, tz: 3 },
  'Москва • Чертаново': { shortRu: 'Чертаново', en: 'Chertanovo', group: 'moscow', lat: 55.6085, lon: 37.6033, tz: 3 },
  'Москва • Ясенево': { shortRu: 'Ясенево', en: 'Yasenevo', group: 'moscow', lat: 55.6063, lon: 37.5332, tz: 3 },
  'Москва • Тёплый Стан': { shortRu: 'Тёплый Стан', en: 'Teply Stan', group: 'moscow', lat: 55.6194, lon: 37.4939, tz: 3 },
  'Москва • Коммунарка': { shortRu: 'Коммунарка', en: 'Kommunarka', group: 'moscow', lat: 55.5694, lon: 37.4867, tz: 3 },
  'Москва • Щербинка': { shortRu: 'Щербинка', en: 'Shcherbinka', group: 'moscow', lat: 55.4997, lon: 37.5597, tz: 3 },
  'Москва • Бирюлёво': { shortRu: 'Бирюлёво', en: 'Biryulyovo', group: 'moscow', lat: 55.5910, lon: 37.6620, tz: 3 },
  'Москва • Марьино': { shortRu: 'Марьино', en: 'Maryino', group: 'moscow', lat: 55.6500, lon: 37.7440, tz: 3 },
  'Москва • Выхино-Жулебино': { shortRu: 'Жулебино', en: 'Zhulebino', group: 'moscow', lat: 55.7010, lon: 37.8320, tz: 3 },
  'Москва • Перово': { shortRu: 'Перово', en: 'Perovo', group: 'moscow', lat: 55.7520, lon: 37.7850, tz: 3 },
  'Москва • Сокольники': { shortRu: 'Сокольники', en: 'Sokolniki', group: 'moscow', lat: 55.7900, lon: 37.6790, tz: 3 },
  'Москва • Отрадное': { shortRu: 'Отрадное', en: 'Otradnoye', group: 'moscow', lat: 55.8640, lon: 37.6050, tz: 3 },
  'Москва • Ховрино': { shortRu: 'Ховрино', en: 'Khovrino', group: 'moscow', lat: 55.8780, lon: 37.4980, tz: 3 },
  'Москва • Митино': { shortRu: 'Митино', en: 'Mitino', group: 'moscow', lat: 55.8458, lon: 37.3619, tz: 3 },
  'Москва • Строгино': { shortRu: 'Строгино', en: 'Strogino', group: 'moscow', lat: 55.8040, lon: 37.4020, tz: 3 },
  'Москва • Кунцево': { shortRu: 'Кунцево', en: 'Kuntsevo', group: 'moscow', lat: 55.7310, lon: 37.4450, tz: 3 },
  'Москва • Раменки': { shortRu: 'Раменки', en: 'Ramenki', group: 'moscow', lat: 55.6980, lon: 37.5060, tz: 3 },
  'Москва • Зеленоград': { shortRu: 'Зеленоград', en: 'Zelenograd', group: 'moscow', lat: 55.9825, lon: 37.1814, tz: 3 },
  'Санкт-Петербург': { shortRu: 'С.-Петербург', en: 'Saint Petersburg', group: 'russia', lat: 59.9343, lon: 30.3351, tz: 3 },
  'Новосибирск': { shortRu: 'Новосибирск', en: 'Novosibirsk', group: 'russia', lat: 55.0084, lon: 82.9357, tz: 7 },
  'Екатеринбург': { shortRu: 'Екатеринбург', en: 'Yekaterinburg', group: 'russia', lat: 56.8389, lon: 60.6057, tz: 5 },
  'Казань': { shortRu: 'Казань', en: 'Kazan', group: 'russia', lat: 55.7887, lon: 49.1221, tz: 3 },
  'Нижний Новгород': { shortRu: 'Н. Новгород', en: 'Nizhny Novgorod', group: 'russia', lat: 56.2965, lon: 43.9361, tz: 3 },
  'Краснодар': { shortRu: 'Краснодар', en: 'Krasnodar', group: 'russia', lat: 45.0355, lon: 38.9753, tz: 3 },
  'Сочи': { shortRu: 'Сочи', en: 'Sochi', group: 'russia', lat: 43.5855, lon: 39.7231, tz: 3 },
  'Самара': { shortRu: 'Самара', en: 'Samara', group: 'russia', lat: 53.1959, lon: 50.1002, tz: 4 },
  'Ростов-на-Дону': { shortRu: 'Ростов-н/Д', en: 'Rostov-on-Don', group: 'russia', lat: 47.2357, lon: 39.7015, tz: 3 },
  'Уфа': { shortRu: 'Уфа', en: 'Ufa', group: 'russia', lat: 54.7388, lon: 55.9721, tz: 5 },
  'Красноярск': { shortRu: 'Красноярск', en: 'Krasnoyarsk', group: 'russia', lat: 56.0153, lon: 92.8932, tz: 7 },
  'Воронеж': { shortRu: 'Воронеж', en: 'Voronezh', group: 'russia', lat: 51.6720, lon: 39.1843, tz: 3 },
  'Пермь': { shortRu: 'Пермь', en: 'Perm', group: 'russia', lat: 58.0105, lon: 56.2502, tz: 5 },
  'Волгоград': { shortRu: 'Волгоград', en: 'Volgograd', group: 'russia', lat: 48.7080, lon: 44.5133, tz: 3 },
  'Владивосток': { shortRu: 'Владивосток', en: 'Vladivostok', group: 'russia', lat: 43.1155, lon: 131.8855, tz: 10 },
  'Калининград': { shortRu: 'Калининград', en: 'Kaliningrad', group: 'russia', lat: 54.7104, lon: 20.4522, tz: 2 },
  'Минск': { shortRu: 'Минск', en: 'Minsk', group: 'russia', lat: 53.9006, lon: 27.5590, tz: 3 },
  'Алматы': { shortRu: 'Алматы', en: 'Almaty', group: 'russia', lat: 43.2220, lon: 76.8512, tz: 5 },
  'Астана': { shortRu: 'Астана', en: 'Astana', group: 'russia', lat: 51.1694, lon: 71.4491, tz: 5 },
  'Ташкент': { shortRu: 'Ташкент', en: 'Tashkent', group: 'russia', lat: 41.2995, lon: 69.2401, tz: 5 }
};

const DEFAULT_CONFIG = {
  boardId: 'cyd_24',
  cydVariant: 's024_perfect', // По умолчанию Профиль 4.1 для матрицы L1435-2.4 (rot=0x60, RGB, INVOFF 0x20, BL=27)
  wifiSsid: '',
  wifiPassword: '',
  yandexApiKey: '',
  city: 'Москва • Бутово',
  latitude: 55.5520,
  longitude: 37.5510,
  timezoneOffset: 3,
  selectedWidget: 'v1_classic_cal',
  autoRotate: false,
  notes: [
    'Утренняя разминка и кофе',
    'Посмотреть задачи на день',
    'Вечерняя прогулка в 19:00'
  ],
  eventTitle: 'До Нового Года',
  eventDays: '73 ДНЯ',
  weatherCache: {
    tempC: 4,
    tmaxC: 6,
    tminC: 1,
    humidity: 72,
    windMs: 3.8,
    wcode: 3,
    descRu: 'Пасмурно',
    source: 'Яндекс Погода'
  }
};

function loadConfig() {
  try {
    if (fs.existsSync(CONFIG_PATH)) {
      const raw = fs.readFileSync(CONFIG_PATH, 'utf-8');
      const parsed = { ...DEFAULT_CONFIG, ...JSON.parse(raw) };
      const validVariants = ['s024_perfect', 's024_bgr_inv0', 's024_rgb_inv1', 's024_bgr_inv1'];
      if (!validVariants.includes(parsed.cydVariant)) {
        parsed.cydVariant = 's024_perfect';
      }
      return parsed;
    }
  } catch (e) {
    console.error('Ошибка чтения config.json:', e.message);
  }
  saveConfig(DEFAULT_CONFIG);
  return JSON.parse(JSON.stringify(DEFAULT_CONFIG));
}

function saveConfig(cfg) {
  try {
    fs.writeFileSync(CONFIG_PATH, JSON.stringify(cfg, null, 2), 'utf-8');
  } catch (e) {
    console.error('Ошибка сохранения config.json:', e.message);
  }
}

function toAsciiSafe(str) {
  if (!str) return '';
  const map = {
    а:'a', б:'b', в:'v', г:'g', д:'d', е:'e', ё:'yo', ж:'zh', з:'z', и:'i', й:'y',
    к:'k', л:'l', м:'m', н:'n', о:'o', п:'p', р:'r', с:'s', т:'t', у:'u', ф:'f',
    х:'kh', ц:'ts', ч:'ch', ш:'sh', щ:'shch', ъ:'', ы:'y', ь:'', э:'e', ю:'yu', я:'ya',
    А:'A', Б:'B', В:'V', Г:'Г', Д:'D', Е:'E', Ё:'Yo', Ж:'Zh', З:'Z', И:'I', Й:'Y',
    К:'K', Л:'L', М:'M', Н:'N', О:'O', П:'P', Р:'R', С:'S', Т:'T', У:'U', Ф:'F',
    Х:'Kh', Ц:'Ts', Ч:'Ch', Ш:'Sh', Щ:'Shch', Ъ:'', Ы:'Y', Ь:'', Э:'E', Ю:'Yu', Я:'Ya'
  };
  return String(str)
    .split('')
    .map(ch => (map[ch] !== undefined ? map[ch] : ch))
    .join('')
    .replace(/[^\x20-\x7E]/g, '');
}

// Генератор скрипта main.py с 10 вариациями часов, календарей и погоды для ESP32-2432S028
function generateCydMainPy(cfg) {
  const cityInfo = CITIES_DB[cfg.city] || {
    en: toAsciiSafe(cfg.city || 'Moscow'),
    lat: Number(cfg.latitude || 55.7558),
    lon: Number(cfg.longitude || 37.6173),
    tz: Number(cfg.timezoneOffset ?? 3)
  };

  const wifiSsid = (cfg.wifiSsid || '').replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  const wifiPass = (cfg.wifiPassword || '').replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  const cityAscii = cityInfo.en;
  const lat = Number(cfg.latitude || cityInfo.lat).toFixed(4);
  const lon = Number(cfg.longitude || cityInfo.lon).toFixed(4);
  const tzOffsetSec = Math.round(Number(cfg.timezoneOffset ?? cityInfo.tz) * 3600);
  const startWidget = cfg.selectedWidget || 'v1_classic_cal';
  const isVariant2 = cfg.cydVariant === 'variant2';

  const notesAscii = (cfg.notes || DEFAULT_CONFIG.notes)
    .slice(0, 3)
    .map(n => toAsciiSafe(n).slice(0, 34));
  while (notesAscii.length < 3) notesAscii.push('Good day!');

  const eventTitle = toAsciiSafe(cfg.eventTitle || 'Countdown').slice(0, 26);
  const eventDays = toAsciiSafe(cfg.eventDays || '73 DAYS').slice(0, 18);

  return `# ============================================================================
# ESP32-2432S028 (CYD 2.8" 320x240) — 10 DESK CLOCK, CALENDAR & WEATHER WIDGETS
# Установлено в 1 клик с веб-сайта
# ============================================================================
import gc
import time
import machine
import lvgl as lv
import lcd_bus
import ili9341
import xpt2046
import task_handler

# Гасим яркий RGB-светодиод на обратной стороне платы CYD (Active LOW: 1 = ВЫКЛ)
for _p in (4, 16, 17):
    try:
        machine.Pin(_p, machine.Pin.OUT, value=1)
    except Exception:
        pass

WIFI_SSID = "${wifiSsid}"
WIFI_PASS = "${wifiPass}"
CITY_NAME = "${cityAscii}"
CITY_LAT = ${lat}
CITY_LON = ${lon}
TZ_OFFSET = ${tzOffsetSec}
START_WIDGET = "${startWidget}"
AUTO_CAROUSEL = ${startWidget === 'v10_carousel' ? 'True' : 'False'}
NOTES_LIST = ${JSON.stringify(notesAscii)}
EVENT_TITLE = "${eventTitle}"
EVENT_DAYS = "${eventDays}"

# Инициализация экрана 320x240 (ILI9341) и сенсора (XPT2046)
spi_bus = machine.SPI.Bus(host=1, mosi=13, miso=12, sck=14)
display_bus = lcd_bus.SPIBus(spi_bus=spi_bus, freq=24000000, dc=2, cs=15)

display = ili9341.ILI9341(
    data_bus=display_bus,
    display_width=320,
    display_height=240,
    backlight_pin=21,
    backlight_on_state=ili9341.STATE_PWM,
    color_space=lv.COLOR_FORMAT.RGB565,
    color_byte_order=${isVariant2 ? 'ili9341.BYTE_ORDER_RGB' : 'ili9341.BYTE_ORDER_BGR'},
    rgb565_byte_swap=1
)
display._ORIENTATION_TABLE = (${isVariant2 ? '0xE0' : '0x20'}, 0x0, 0x0, 0x0)
display.set_rotation(lv.DISPLAY_ROTATION._0)
display.set_power(True)
display.init(1)
display.set_backlight(100)

indev_bus = machine.SPI.Bus(host=2, mosi=32, miso=39, sck=25)
indev_dev = machine.SPI.Device(spi_bus=indev_bus, freq=2000000, cs=33)
indev = xpt2046.XPT2046(device=indev_dev)

th = task_handler.TaskHandler()

state = {
    "temp": ${cfg.weatherCache?.tempC ?? 14},
    "wind": ${cfg.weatherCache?.windMs ?? 3.5},
    "hum": 64,
    "tmax": ${(cfg.weatherCache?.tempC ?? 14) + 3},
    "tmin": ${(cfg.weatherCache?.tempC ?? 14) - 2},
    "wifi_ok": False,
    "pomo_sec": 25 * 60,
    "pomo_run": False,
    "carousel_ticks": 0
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
scr.remove_flag(lv.obj.FLAG.SCROLLABLE)

# Верхняя строка статуса (320x24)
top = lv.obj(scr)
top.remove_style_all()
top.set_size(320, 24)
top.set_pos(0, 0)
top.set_style_bg_color(lv.color_hex(0x101C33), 0)
top.set_style_bg_opa(255, 0)

lbl_top_left = lv.label(top)
lbl_top_left.set_text("1/9 CALENDAR & CLOCK")
lbl_top_left.set_style_text_color(lv.color_hex(0x00E5FF), 0)
lbl_top_left.set_style_text_font(lv.font_montserrat_12, 0)
lbl_top_left.align(lv.ALIGN.LEFT_MID, 8, 0)

lbl_top_right = lv.label(top)
lbl_top_right.set_text(CITY_NAME[:14])
lbl_top_right.set_style_text_color(lv.color_hex(0x10B981), 0)
lbl_top_right.set_style_text_font(lv.font_montserrat_12, 0)
lbl_top_right.align(lv.ALIGN.RIGHT_MID, -8, 0)

# Рабочая область виджета (320x182)
body = lv.obj(scr)
body.remove_style_all()
body.set_size(320, 182)
body.set_pos(0, 24)

# Нижняя сенсорная панель переключения между всеми 9 видами часов и календарей (320x34)
nav = lv.obj(scr)
nav.remove_style_all()
nav.set_size(320, 34)
nav.set_pos(0, 206)
nav.set_style_bg_color(lv.color_hex(0x0E172A), 0)
nav.set_style_bg_opa(255, 0)

def get_dt(extra_hours=0):
    return time.localtime(time.time() + TZ_OFFSET + extra_hours * 3600)

def fmt_temp(v):
    return ("+{:.0f} C" if v > 0 else "{:.0f} C").format(v)

# 1. Классический календарь + часы + погода
def build_v1():
    lbl_top_left.set_text("1/9 CLASSIC CALENDAR")
    t = get_dt()
    left = lv.obj(body)
    left.remove_style_all()
    left.set_size(134, 174)
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

    cal = lv.calendar(body)
    cal.set_size(174, 170)
    cal.set_pos(142, 6)
    cal.set_today_date(t[0], t[1], t[2])
    cal.set_showed_date(t[0], t[1])
    cal.set_style_bg_color(lv.color_hex(0x0D1526), 0)
    cal.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    cal.set_style_border_color(lv.color_hex(0x1E3A5F), 0)
    cal.set_style_text_font(lv.font_montserrat_10, 0)

# 2. Гигантские Flip-часы + погода
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

# 3. Отрывной календарь дня
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

# 4. Метеостанция Pro + прогноз
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

# 5. Органайзер дня: Часы + Погода + Заметки
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
        nl.set_text("[{}] {}".format(i + 1, note))
        nl.set_style_text_font(lv.font_montserrat_14, 0)
        nl.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        nl.align(lv.ALIGN.LEFT_MID, 12, 0)

# 6. Мировые часы (3 часовых пояса) + погода
def build_v6():
    lbl_top_left.set_text("6/9 WORLD CLOCK (3 ZONES)")
    t_local = get_dt(0)
    t_utc = time.localtime(time.time())
    t_tokyo = time.localtime(time.time() + 9 * 3600)

    zones = [
        (CITY_NAME[:12], t_local, 0x00E5FF),
        ("London / UTC", t_utc, 0x10B981),
        ("Tokyo (JST)", t_tokyo, 0xFBBF24)
    ]
    for i, (zname, zt, col) in enumerate(zones):
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
        zv.set_text("{:02d}:{:02d}".format(zt[3], zt[4]))
        zv.set_style_text_font(lv.font_montserrat_28, 0)
        zv.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        zv.align(lv.ALIGN.RIGHT_MID, -14, 0)

# 7. Счётчик дней до события + Часы
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

# 8. Сенсорный Помодоро-таймер + Настольные часы
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

# 9. Ночные янтарные часы + календарь-строка
def build_v9():
    lbl_top_left.set_text("9/9 NIGHT AMBER CLOCK")
    t = get_dt()
    nc = lv.label(body)
    nc.set_text("{:02d}:{:02d}".format(t[3], t[4]))
    nc.set_style_text_font(lv.font_montserrat_48, 0)
    nc.set_style_text_color(lv.color_hex(0xFFB000), 0)
    nc.align(lv.ALIGN.CENTER, 0, -20)

    nd = lv.label(body)
    nd.set_text("{} {:02d}.{:02d}.{:04d}  •  {}".format(DAYS_EN[t[6] % 7], t[2], t[1], t[0], fmt_temp(state["temp"])))
    nd.set_style_text_font(lv.font_montserrat_16, 0)
    nd.set_style_text_color(lv.color_hex(0xB45309), 0)
    nd.align(lv.ALIGN.CENTER, 0, 36)

BUILDERS = [
    build_v1, build_v2, build_v3, build_v4, build_v5,
    build_v6, build_v7, build_v8, build_v9
]

def render_current():
    body.clean()
    BUILDERS[current_idx % len(BUILDERS)]()

# Сенсорные кнопки [< Prev] [Стиль 1..9] [Next >] внизу экрана
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

# Подключение к Wi-Fi и получение погоды Open-Meteo + точного времени NTP
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
            for _ in range(25):
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
            lbl_top_right.set_text("Offline")
    except Exception:
        pass

connect_wifi_and_fetch()

def tick_cb(t):
    global current_idx
    if state["pomo_run"] and state["pomo_sec"] > 0:
        state["pomo_sec"] -= 1
        if current_idx == 7:
            render_current()

    state["carousel_ticks"] += 1
    if AUTO_CAROUSEL and state["carousel_ticks"] % 12 == 0:
        current_idx = (current_idx + 1) % len(BUILDERS)
        render_current()
    elif state["carousel_ticks"] % 30 == 0:
        render_current()

timer_sec = lv.timer_create(tick_cb, 1000, None)
timer_sec.set_repeat_count(-1)
print("CYD_WIDGET_ENGINE_READY")
`;
}

function getLocalNetworkIps() {
  const nets = os.networkInterfaces();
  const results = [];
  for (const name of Object.keys(nets)) {
    for (const net of nets[name]) {
      if (net.family === 'IPv4' && !net.internal) {
        results.push({ interface: name, address: net.address });
      }
    }
  }
  return results;
}

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.bin': 'application/octet-stream',
  '.py': 'text/plain; charset=utf-8'
};

function sendJson(res, status, data) {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type'
  });
  res.end(JSON.stringify(data));
}

function parseBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => {
      body += chunk.toString();
      if (body.length > 2 * 1024 * 1024) reject(new Error('Payload too large'));
    });
    req.on('end', () => {
      if (!body) return resolve({});
      try {
        resolve(JSON.parse(body));
      } catch (e) {
        reject(e);
      }
    });
    req.on('error', reject);
  });
}

const YANDEX_COND_MAP = {
  'clear': { descRu: 'Ясно', wcode: 0 },
  'partly-cloudy': { descRu: 'Малооблачно', wcode: 2 },
  'cloudy': { descRu: 'Облачно', wcode: 2 },
  'overcast': { descRu: 'Пасмурно', wcode: 3 },
  'light-rain': { descRu: 'Небольшой дождь', wcode: 61 },
  'rain': { descRu: 'Дождь', wcode: 63 },
  'heavy-rain': { descRu: 'Сильный дождь', wcode: 65 },
  'showers': { descRu: 'Ливень', wcode: 80 },
  'wet-snow': { descRu: 'Дождь со снегом', wcode: 68 },
  'light-snow': { descRu: 'Небольшой снег', wcode: 71 },
  'snow': { descRu: 'Снег', wcode: 73 },
  'snow-showers': { descRu: 'Снегопад', wcode: 75 },
  'hail': { descRu: 'Град', wcode: 96 },
  'thunderstorm': { descRu: 'Гроза', wcode: 95 },
  'thunderstorm-with-rain': { descRu: 'Дождь с грозой', wcode: 95 },
  'thunderstorm-with-hail': { descRu: 'Гроза с градом', wcode: 99 }
};

function wmoToRu(wcode) {
  if (wcode === 0) return 'Ясно';
  if (wcode === 1 || wcode === 2) return 'Малооблачно';
  if (wcode === 3) return 'Пасмурно';
  if (wcode === 45 || wcode === 48) return 'Туман';
  if (wcode >= 51 && wcode <= 57) return 'Морось';
  if (wcode >= 61 && wcode <= 67) return 'Дождь';
  if (wcode >= 71 && wcode <= 77) return 'Снег';
  if (wcode >= 80 && wcode <= 82) return 'Ливень';
  if (wcode >= 85 && wcode <= 86) return 'Снегопад';
  if (wcode >= 95) return 'Гроза';
  return 'Облачно';
}

function httpsGetText(urlStr, headers = {}, timeoutMs = 2200, maxRedirects = 2) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error('Hard timeout'));
    }, timeoutMs);
    const req = https.get(urlStr, {
      headers: {
        'User-Agent': 'ESP32-CYD-Weather-Station/2.0 (https://github.com/e6six/esp32)',
        'Accept-Language': 'ru-RU,ru;q=0.9',
        ...headers
      },
      timeout: timeoutMs
    }, res => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location && maxRedirects > 0) {
        clearTimeout(timer);
        const nextUrl = new URL(res.headers.location, urlStr).toString();
        res.resume();
        return httpsGetText(nextUrl, headers, timeoutMs, maxRedirects - 1).then(resolve).catch(reject);
      }
      let data = '';
      res.on('data', chunk => {
        data += chunk.toString('utf-8');
        if (data.length > 300000) req.destroy();
      });
      res.on('end', () => {
        clearTimeout(timer);
        resolve({ status: res.statusCode, body: data });
      });
    });
    req.on('timeout', () => { clearTimeout(timer); req.destroy(); reject(new Error('Timeout')); });
    req.on('error', err => { clearTimeout(timer); reject(err); });
  });
}

async function fetchYandexOrHyperlocalWeather(lat, lon) {
  // 1. Бесплатная метеостанция Open-Meteo + Росгидромет WMO по координатам района (с ветром в м/с)
  try {
    const omUrl = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true&windspeed_unit=ms`;
    const r = await httpsGetText(omUrl, {}, 2200);
    if (r.status === 200) {
      const j = JSON.parse(r.body);
      const cw = j.current_weather;
      if (cw) {
        const tempC = Math.round(Number(cw.temperature ?? 4));
        const wcode = Number(cw.weathercode ?? 3);
        return {
          tempC,
          tmaxC: tempC + 2,
          tminC: tempC - 2,
          windMs: Number(Number(cw.windspeed ?? 3.5).toFixed(1)),
          humidity: 70,
          wcode,
          descRu: wmoToRu(wcode),
          source: 'Метеостанция (Open-Meteo WMO)'
        };
      }
    }
  } catch (e) {
    // ignore
  }
  return null;
}

const server = http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    return res.end();
  }

  const parsedUrl = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const pathname = parsedUrl.pathname;

  try {
    if (pathname === '/api/status' && req.method === 'GET') {
      const cfg = loadConfig();
      return sendJson(res, 200, {
        ok: true,
        localIps: getLocalNetworkIps(),
        port: PORT,
        cities: CITIES_DB,
        config: cfg,
        mainPy: generateCydMainPy(cfg)
      });
    }

    if (pathname === '/api/weather' && req.method === 'GET') {
      const cfg = loadConfig();
      const cityKey = parsedUrl.searchParams.get('city') || cfg.city || 'Москва • Бутово';
      const cityInfo = CITIES_DB[cityKey] || CITIES_DB['Москва • Бутово'] || { lat: 55.5520, lon: 37.5510 };
      const lat = Number(parsedUrl.searchParams.get('lat') || cityInfo.lat || cfg.latitude || 55.5520);
      const lon = Number(parsedUrl.searchParams.get('lon') || cityInfo.lon || cfg.longitude || 37.5510);
      const yandexKey = parsedUrl.searchParams.get('yandexKey') ?? cfg.yandexApiKey ?? '';
      const weather = await fetchYandexOrHyperlocalWeather(lat, lon, yandexKey);
      if (weather) {
        cfg.weatherCache = { ...cfg.weatherCache, ...weather, updatedAt: Date.now() };
        saveConfig(cfg);
      }
      return sendJson(res, 200, {
        ok: true,
        city: cityKey,
        shortRu: cityInfo.shortRu || cityKey,
        lat,
        lon,
        weather: weather || cfg.weatherCache
      });
    }

    if (pathname === '/api/config' && req.method === 'POST') {
      const body = await parseBody(req);
      const current = loadConfig();
      const updated = { ...current, ...body };
      if (updated.city && CITIES_DB[updated.city]) {
        updated.latitude = CITIES_DB[updated.city].lat;
        updated.longitude = CITIES_DB[updated.city].lon;
        updated.timezoneOffset = CITIES_DB[updated.city].tz;
      }
      saveConfig(updated);
      return sendJson(res, 200, {
        ok: true,
        config: updated,
        mainPy: generateCydMainPy(updated)
      });
    }

    let filePath = pathname === '/' ? path.join(PUBLIC_DIR, 'index.html') : path.join(PUBLIC_DIR, pathname);
    if (!filePath.startsWith(PUBLIC_DIR)) {
      res.writeHead(403);
      return res.end('Forbidden');
    }

    if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
      const ext = path.extname(filePath).toLowerCase();
      const contentType = MIME_TYPES[ext] || 'application/octet-stream';
      const stat = fs.statSync(filePath);
      res.writeHead(200, {
        'Content-Type': contentType,
        'Content-Length': stat.size,
        'Cache-Control': 'no-store, no-cache, must-revalidate'
      });
      fs.createReadStream(filePath).pipe(res);
    } else {
      const indexFile = path.join(PUBLIC_DIR, 'index.html');
      res.writeHead(200, {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-store, no-cache, must-revalidate'
      });
      fs.createReadStream(indexFile).pipe(res);
    }
  } catch (err) {
    console.error('Server error:', err);
    sendJson(res, 500, { ok: false, error: err.message });
  }
});

server.listen(PORT, HOST, () => {
  console.log(`🚀 Сайт установки часов, календарей и погоды для ESP32-2432S028 запущен: http://localhost:${PORT}`);
});
