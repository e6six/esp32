/*
 * ============================================================================
 *  ESP32 HARDWARE SCANNER — Диагностический скетч для неизвестной платы с экраном
 * ============================================================================
 *  Загрузите этот скетч на вашу подарочную плату ESP32, если не знаете её модель.
 *  Он автоматически:
 *    1. Определит точную модель процессора ESP32, ревизию, объём Flash и PSRAM
 *    2. Просканирует шину I2C на популярных пинах (найдёт OLED 0x3C, тачскрин, датчики)
 *    3. Проверит пины подсветки популярных экранов (GPIO 21, 4, 38, 5, 15, 27)
 *    4. Отправит полный JSON-отчёт на наш веб-сайт (вкладка «Сканер устройства»)!
 * ============================================================================
 */

#include <Arduino.h>
#include <Wire.h>

const int BACKLIGHT_CANDIDATES[] = {21, 4, 38, 5, 15, 27, 2};
const int NUM_BL_PINS = sizeof(BACKLIGHT_CANDIDATES) / sizeof(BACKLIGHT_CANDIDATES[0]);

struct I2cPair {
  int sda;
  int scl;
  const char* label;
};

const I2cPair I2C_CANDIDATES[] = {
  {21, 22, "Стандартные I2C (GPIO 21/22 — OLED SSD1306 / NodeMCU)"},
  {33, 32, "Сенсор/периферия CYD (GPIO 33/32)"},
  {18, 17, "ESP32-S3 Touch I2C (GPIO 18/17)"},
  {4,  15, "Heltec WiFi Kit 32 OLED (GPIO 4/15)"},
  {5,  4,  "Wemos Lolin32 OLED (GPIO 5/4)"}
};

void scanI2cBus(int sda, int scl, const char* label) {
  Wire.begin(sda, scl, 100000);
  bool foundAny = false;
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      if (!foundAny) {
        Serial.printf("  [+] Шина %s:\n", label);
        foundAny = true;
      }
      Serial.printf("      Найдено I2C-устройство: 0x%02X ", addr);
      if (addr == 0x3C || addr == 0x3D) Serial.print("-> ЭКРАН OLED SSD1306 / SH1106 (128x64)!");
      else if (addr == 0x38 || addr == 0x15) Serial.print("-> Емкостный тачскрин (FT6236 / CST816S)!");
      else if (addr == 0x5D || addr == 0x14) Serial.print("-> Емкостный тачскрин GT911!");
      else if (addr == 0x68) Serial.print("-> Часы реального времени DS3231 или гироскоп MPU6050");
      else if (addr == 0x76 || addr == 0x77) Serial.print("-> Датчик погоды BME280 / BMP280");
      Serial.println();
    }
  }
  Wire.end();
}

void runFullScan() {
  Serial.println("\n============================================================");
  Serial.println("🔍 ДИАГНОСТИКА НЕИЗВЕСТНОЙ ПЛАТЫ ESP32 С ЭКРАНОМ");
  Serial.println("============================================================");

#if defined(ESP32)
  String chipModel = ESP.getChipModel();
  uint8_t chipRev = ESP.getChipRevision();
  uint32_t flashMb = ESP.getFlashChipSize() / (1024 * 1024);
  uint32_t psramKb = ESP.getPsramSize() / 1024;
  uint64_t mac = ESP.getEfuseMac();

  Serial.printf("Чип          : %s (ревизия v%d)\n", chipModel.c_str(), chipRev);
  Serial.printf("Частота CPU  : %u МГц, Ядер: %d\n", ESP.getCpuFreqMHz(), ESP.getChipCores());
  Serial.printf("Flash-память : %u МБ\n", flashMb);
  Serial.printf("PSRAM-память : %u КБ %s\n", psramKb, psramKb > 0 ? "(ЕСТЬ PSRAM — часто на S3/T-Display)" : "(нет внешней PSRAM)");
  Serial.printf("MAC-адрес    : %04X%08X\n", (uint16_t)(mac >> 32), (uint32_t)mac);
#endif

  Serial.println("\n--- Этап 1: Сканирование шин I2C (поиск OLED и тачскрина) ---");
  for (size_t i = 0; i < sizeof(I2C_CANDIDATES) / sizeof(I2C_CANDIDATES[0]); i++) {
    scanI2cBus(I2C_CANDIDATES[i].sda, I2C_CANDIDATES[i].scl, I2C_CANDIDATES[i].label);
  }

  Serial.println("\n--- Этап 2: Проверка пинов подсветки экрана (Backlight) ---");
  Serial.println("Смотрите на экран платы: на каком пине загорится подсветка?");
  for (int i = 0; i < NUM_BL_PINS; i++) {
    int pin = BACKLIGHT_CANDIDATES[i];
    Serial.printf("  -> Включаем GPIO %d на 600 мс... ", pin);
    if (pin == 21) Serial.println("(если экран засветился — это жёлтая плата CYD ESP32-2432S028 2.8\"!)");
    else if (pin == 4) Serial.println("(если экран засветился — это LilyGO TTGO T-Display 1.14\"!)");
    else if (pin == 38) Serial.println("(если экран засветился — это LilyGO T-Display-S3 1.9\"!)");
    else if (pin == 5) Serial.println("(если экран засветился — это кубик GeekMagic SmallTV 1.54\"!)");
    else Serial.println();

    pinMode(pin, OUTPUT);
    digitalWrite(pin, HIGH);
    delay(600);
  }

  // JSON-пакет для автоматического распознавания на нашем веб-сайте
#if defined(ESP32)
  Serial.printf("{\"cmd\":\"scan_report\",\"chip\":\"%s\",\"flashMb\":%u,\"psramKb\":%u}\n",
                ESP.getChipModel(),
                ESP.getFlashChipSize() / (1024 * 1024),
                ESP.getPsramSize() / 1024);
#endif
  Serial.println("============================================================\n");
}

void setup() {
  Serial.begin(115200);
  delay(800);
  runFullScan();
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() > 0) {
      runFullScan();
    }
  }
  delay(5000);
  runFullScan();
}
