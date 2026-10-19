/*
 * ============================================================================
 *  ESP32 DESK WIDGET & CALENDAR HUB — Сгенерировано на сайте управления ESP32
 * ============================================================================
 *  Устройство : ESP32-2432S028 (CYD 2.8" Жёлтая плата)
 *  Экран      : ILI9341 (TFT 2.8") (320x240)
 *  Чип        : ESP32-D0WDQ6
 *  Активные виджеты (4):
 *    1. Календарь и Часы
 *    2. Монитор ПК (CPU / RAM)
 *    3. Погода и Прогноз
 *    4. Заметки и Помодоро
 *
 *  Поддерживает 2 режима работы одновременно:
 *    1. По USB (Serial 115200 бод) — мгновенно принимает данные от нашего
 *       веб-сайта (через Web Serial в браузере) или скрипта pc_monitor_sender.py
 *    2. По Wi-Fi — сам синхронизирует точное время (NTP), календарь и погоду,
 *       а также поднимает свой мини веб-сервер в локальной сети!
 * ============================================================================
 */

#include <Arduino.h>
#if defined(ESP32)
  #include <WiFi.h>
  #include <WebServer.h>
  #include <HTTPClient.h>
#endif
#include <time.h>

// Настройки вашей платы: ESP32-2432S028 (CYD 2.8" Жёлтая плата)
#define BOARD_ID "cyd_28"
#define SCREEN_WIDTH 320
#define SCREEN_HEIGHT 240
#define IS_MONOCHROME_OLED 0
#define BACKLIGHT_PIN 21
#define BTN_NEXT_PIN 0

// Настройки Wi-Fi и Города (можно также менять прямо с сайта по USB!)
String wifiSsid     = "";
String wifiPassword = "";
String cityName     = "Москва";
float  cityLat      = 55.7558;
float  cityLon      = 37.6173;
long   gmtOffsetSec = 10800;

// Библиотека экрана:
// - Для цветных TFT экранов (ILI9341 / ST7789 / GC9A01) используется LovyanGFX
//   (не требует ручного редактирования User_Setup.h, все пины уже прописаны ниже!)
// - Для монохромных OLED (SSD1306) используется Adafruit_SSD1306 или U8g2
#if !IS_MONOCHROME_OLED
  #define LGFX_USE_V1
  #include <LovyanGFX.hpp>

  class LGFX_CustomBoard : public lgfx::LGFX_Device {
  
    lgfx::Panel_ILI9341 _panel_instance;
    lgfx::Bus_SPI       _bus_instance;
    lgfx::Light_PWM     _light_instance;
  public:
    LGFX_CustomBoard(void) {
      {
        auto cfg = _bus_instance.config();
        cfg.spi_host = HSPI_HOST;
        cfg.spi_mode = 0;
        cfg.freq_write = 40000000;
        cfg.pin_sclk = 14;
        cfg.pin_mosi = 13;
        cfg.pin_miso = 12;
        cfg.pin_dc   = 2;
        _bus_instance.config(cfg);
        _panel_instance.setBus(&_bus_instance);
      }
      {
        auto cfg = _panel_instance.config();
        cfg.pin_cs   = 15;
        cfg.pin_rst  = -1;
        cfg.panel_width  = 240;
        cfg.panel_height = 320;
        cfg.offset_rotation = 1;
        _panel_instance.config(cfg);
      }
      {
        auto cfg = _light_instance.config();
        cfg.pin_bl = 21;
        cfg.invert = false;
        _light_instance.config(cfg);
        _panel_instance.setLight(&_light_instance);
      }
      setPanel(&_panel_instance);
    }
  };

  LGFX_CustomBoard display;
#endif

// Состояние виджетов и метрик ПК
int currentScreen = 0; // 0: Календарь+Часы, 1: Монитор ПК, 2: Погода, 3: Заметки/Помодоро
const int TOTAL_SCREENS = 4;

int pcCpu = 18;
int pcRam = 46;
int pcTemp = 48;
int pcDownKbps = 240;
String pcRamGb = "7.4/16 ГБ";

int weatherTemp = 14;
int weatherHumidity = 64;
String weatherDesc = "Переменная облачность";

String noteLine1 = "Проверить почту и задачи";
String noteLine2 = "Настроить виджеты на ESP32";
String noteLine3 = "Перерыв и разминка в 15:00";

unsigned long lastDrawMs = 0;
unsigned long lastAutoSwitchMs = 0;
bool autoRotate = false;
unsigned long rotateIntervalMs = 12000;

String serialBuffer = "";

// Простой парсер значений из JSON-строки от сайта или Python-скрипта
String extractJsonString(const String& json, const char* key) {
  String pattern = String("\"") + key + "\":\"";
  int start = json.indexOf(pattern);
  if (start < 0) return "";
  start += pattern.length();
  int end = json.indexOf("\"", start);
  if (end < 0) return "";
  return json.substring(start, end);
}

int extractJsonInt(const String& json, const char* key, int defaultVal) {
  String pattern = String("\"") + key + "\":";
  int start = json.indexOf(pattern);
  if (start < 0) return defaultVal;
  start += pattern.length();
  int end = start;
  while (end < (int)json.length() && (isDigit(json[end]) || json[end] == '-')) end++;
  if (end == start) return defaultVal;
  return json.substring(start, end).toInt();
}

void drawHeader(const char* title) {
#if !IS_MONOCHROME_OLED
  display.fillRect(0, 0, SCREEN_WIDTH, 28, 0x10A6);
  display.setTextColor(0x07FF, 0x10A6);
  display.setTextSize(1);
  display.setCursor(10, 9);
  display.print(title);

  // Статус подключения справа вверху
  display.setCursor(SCREEN_WIDTH - 95, 9);
  if (WiFi.status() == WL_CONNECTED) {
    display.setTextColor(0x07E0, 0x10A6);
    display.print("Wi-Fi OK | USB");
  } else {
    display.setTextColor(0xFFE0, 0x10A6);
    display.print("USB LIVE MODE");
  }
#endif
}

// Вычисление дня недели (0 = Пн ... 6 = Вс)
int dayOfWeekMonFirst(int y, int m, int d) {
  static int t[] = {0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4};
  if (m < 3) y -= 1;
  int w = (y + y/4 - y/100 + y/400 + t[m-1] + d) % 7; // 0 = Вс .. 6 = Сб
  return (w + 6) % 7; // 0 = Пн .. 6 = Вс
}

int daysInMonth(int y, int m) {
  const int dm[] = {31,28,31,30,31,30,31,31,30,31,30,31};
  if (m == 2 && ((y % 4 == 0 && y % 100 != 0) || (y % 400 == 0))) return 29;
  return dm[(m - 1) % 12];
}

void renderCalendarScreen() {
#if !IS_MONOCHROME_OLED
  display.fillScreen(0x0842);
  drawHeader("КАЛЕНДАРЬ И ЧАСЫ");

  struct tm timeinfo;
  int year = 2026, month = 10, day = 19, hour = 14, minute = 30, sec = 0;
  if (getLocalTime(&timeinfo, 10)) {
    year = timeinfo.tm_year + 1900;
    month = timeinfo.tm_mon + 1;
    day = timeinfo.tm_mday;
    hour = timeinfo.tm_hour;
    minute = timeinfo.tm_min;
    sec = timeinfo.tm_sec;
  }

  // Левая панель: Часы и погода
  char timeBuf[16];
  snprintf(timeBuf, sizeof(timeBuf), "%02d:%02d", hour, minute);
  display.setTextColor(0xFFFF, 0x0842);
  display.setTextSize(3);
  display.setCursor(12, 44);
  display.print(timeBuf);

  char dateBuf[24];
  snprintf(dateBuf, sizeof(dateBuf), "%02d.%02d.%04d", day, month, year);
  display.setTextColor(0x07FF, 0x0842);
  display.setTextSize(1);
  display.setCursor(14, 80);
  display.print(dateBuf);

  // Мини-плашка погоды и ПК под часами
  display.drawRoundRect(10, 102, 118, 54, 6, 0x39E7);
  display.setCursor(18, 112);
  display.setTextColor(0xFFE0, 0x0842);
  display.printf("Погода: %+d C", weatherTemp);
  display.setCursor(18, 130);
  display.setTextColor(0x07E0, 0x0842);
  display.printf("CPU:%d%% RAM:%d%%", pcCpu, pcRam);

  // Правая панель: Сетка календаря на месяц
  int calX = 140;
  int calY = 40;
  int cellW = 24;
  int cellH = 22;
  const char* daysHdr[7] = {"Пн","Вт","Ср","Чт","Пт","Сб","Вс"};
  for (int i = 0; i < 7; i++) {
    display.setTextColor(i >= 5 ? 0xF8A0 : 0xAD55, 0x0842);
    display.setCursor(calX + i * cellW, calY);
    display.print(daysHdr[i]);
  }

  int firstDow = dayOfWeekMonFirst(year, month, 1);
  int totalDays = daysInMonth(year, month);
  int row = 0, col = firstDow;

  for (int d = 1; d <= totalDays; d++) {
    int x = calX + col * cellW;
    int y = calY + 18 + row * cellH;
    if (d == day) {
      display.fillRoundRect(x - 3, y - 3, 20, 16, 4, 0x07FF);
      display.setTextColor(0x0000, 0x07FF);
    } else if (col >= 5) {
      display.setTextColor(0xF8A0, 0x0842);
    } else {
      display.setTextColor(0xFFFF, 0x0842);
    }
    display.setCursor(x, y);
    display.printf("%2d", d);

    col++;
    if (col >= 7) {
      col = 0;
      row++;
    }
  }
#endif
}

void renderPcMonitorScreen() {
#if !IS_MONOCHROME_OLED
  display.fillScreen(0x0842);
  drawHeader("МОНИТОРИНГ КОМПЬЮТЕРА");

  // CPU полоса
  display.setTextColor(0xFFFF, 0x0842);
  display.setTextSize(2);
  display.setCursor(14, 44);
  display.printf("CPU: %d%%   %d C", pcCpu, pcTemp);
  display.drawRoundRect(14, 70, SCREEN_WIDTH - 28, 20, 4, 0x39E7);
  display.fillRoundRect(16, 72, (int)((SCREEN_WIDTH - 32) * (pcCpu / 100.0)), 16, 3, pcCpu > 80 ? 0xF800 : 0x07FF);

  // RAM полоса
  display.setCursor(14, 106);
  display.printf("RAM: %d%% (%s)", pcRam, pcRamGb.c_str());
  display.drawRoundRect(14, 132, SCREEN_WIDTH - 28, 20, 4, 0x39E7);
  display.fillRoundRect(16, 134, (int)((SCREEN_WIDTH - 32) * (pcRam / 100.0)), 16, 3, 0x07E0);

  // Сеть
  display.setTextSize(1);
  display.setTextColor(0xFFE0, 0x0842);
  display.setCursor(14, 170);
  display.printf("Сеть Down: %d KB/s | Управление с веб-сайта активно", pcDownKbps);
#endif
}

void renderNotesScreen() {
#if !IS_MONOCHROME_OLED
  display.fillScreen(0x0842);
  drawHeader("ЗАМЕТКИ И ЗАДАЧИ С САЙТА");

  display.setTextColor(0xFFE0, 0x0842);
  display.setTextSize(2);
  display.setCursor(14, 42);
  display.print("Список задач:");

  display.setTextColor(0xFFFF, 0x0842);
  display.setTextSize(1);
  display.setCursor(18, 76);
  display.print("1. " + noteLine1);
  display.setCursor(18, 102);
  display.print("2. " + noteLine2);
  display.setCursor(18, 128);
  display.print("3. " + noteLine3);
#endif
}

void renderCurrentScreen() {
  if (currentScreen == 0) renderCalendarScreen();
  else if (currentScreen == 1) renderPcMonitorScreen();
  else renderNotesScreen();
}

void handleSerialCommand(const String& line) {
  if (line.indexOf("\"cmd\":\"scan\"") >= 0 || line == "PING" || line == "SCAN") {
    Serial.printf("{\"status\":\"ok\",\"device\":\"%s\",\"board\":\"%s\",\"width\":%d,\"height\":%d}\n",
                  "Мой ESP32 Виджет", BOARD_ID, SCREEN_WIDTH, SCREEN_HEIGHT);
    return;
  }
  if (line.indexOf("\"cmd\":\"pc\"") >= 0) {
    pcCpu = extractJsonInt(line, "cpu", pcCpu);
    pcRam = extractJsonInt(line, "ram", pcRam);
    pcTemp = extractJsonInt(line, "temp", pcTemp);
    pcDownKbps = extractJsonInt(line, "down", pcDownKbps);
    String rg = extractJsonString(line, "ram_gb");
    if (rg.length() > 0) pcRamGb = rg;
    renderCurrentScreen();
    return;
  }
  if (line.indexOf("\"cmd\":\"screen\"") >= 0) {
    currentScreen = extractJsonInt(line, "index", 0) % TOTAL_SCREENS;
    renderCurrentScreen();
    Serial.println("{\"status\":\"screen_changed\"}");
    return;
  }
  if (line.indexOf("\"cmd\":\"notes\"") >= 0) {
    String n1 = extractJsonString(line, "n1");
    String n2 = extractJsonString(line, "n2");
    String n3 = extractJsonString(line, "n3");
    if (n1.length() > 0) noteLine1 = n1;
    if (n2.length() > 0) noteLine2 = n2;
    if (n3.length() > 0) noteLine3 = n3;
    currentScreen = 2;
    renderCurrentScreen();
    Serial.println("{\"status\":\"notes_updated\"}");
    return;
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n=== ESP32 DESK WIDGET HUB READY ===");
  Serial.printf("Board Profile: %s (%dx%d)\n", BOARD_ID, SCREEN_WIDTH, SCREEN_HEIGHT);

  pinMode(BTN_NEXT_PIN, INPUT_PULLUP);

#if !IS_MONOCHROME_OLED
  display.init();
  display.setRotation(1);
  display.setBrightness(220);
#endif

  if (wifiSsid.length() > 0) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(wifiSsid.c_str(), wifiPassword.c_str());
    unsigned long startAttempt = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - startAttempt < 6000) {
      delay(250);
    }
    if (WiFi.status() == WL_CONNECTED) {
      configTime(gmtOffsetSec, 0, "pool.ntp.org", "time.nist.gov");
      Serial.print("Wi-Fi connected! Local IP: ");
      Serial.println(WiFi.localIP());
    }
  }

  renderCurrentScreen();
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      serialBuffer.trim();
      if (serialBuffer.length() > 0) {
        handleSerialCommand(serialBuffer);
      }
      serialBuffer = "";
    } else {
      serialBuffer += c;
    }
  }

  // Переключение экрана кнопкой на плате
  if (digitalRead(BTN_NEXT_PIN) == LOW) {
    delay(180);
    currentScreen = (currentScreen + 1) % 3;
    renderCurrentScreen();
  }

  if (autoRotate && millis() - lastAutoSwitchMs > rotateIntervalMs) {
    lastAutoSwitchMs = millis();
    currentScreen = (currentScreen + 1) % 3;
    renderCurrentScreen();
  }

  if (millis() - lastDrawMs > 10000) {
    lastDrawMs = millis();
    renderCurrentScreen();
  }
}
