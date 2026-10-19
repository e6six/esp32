#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Автоматический USB-сканер для определения неизвестной платы ESP32 / ESP8266 с экраном.
Запуск на вашем компьютере:
    pip install pyserial esptool
    python scan_esp32.py
"""

import sys
import time
import subprocess
import re

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("❌ Не установлена библиотека pyserial.")
    print("Установите её командой: pip install pyserial esptool")
    sys.exit(1)


KNOWN_USB_BRIDGES = {
    (0x10C4, 0xEA60): "Silicon Labs CP2102 / CP2104 (часто на TTGO T-Display, NodeMCU-32S, OLED-платах)",
    (0x1A86, 0x7523): "WCH CH340G / CH340C (очень часто на жёлтой плате CYD ESP32-2432S028, GeekMagic SmallTV)",
    (0x1A86, 0x55D4): "WCH CH9102F / CH9102X (часто на LilyGO T-Display v1.1, новых ревизиях CYD с Type-C)",
    (0x303A, 0x1001): "Espressif Native USB JTAG/Serial (встроенный USB на ESP32-S3 / ESP32-C3 / ESP32-C6)",
    (0x303A, 0x0002): "Espressif ESP32-S2 Native USB",
    (0x0403, 0x6001): "FTDI FT232RL",
}


def analyze_boot_log(log_text: str):
    """Анализирует загрузочный лог ESP32 после перезагрузки."""
    hints = []
    chip_type = None

    if "ESP-ROM:esp32s3" in log_text or "chip revision: v" in log_text and "esp32s3" in log_text.lower():
        chip_type = "ESP32-S3"
        hints.append("Обнаружен чип ESP32-S3 (часто это LilyGO T-Display-S3 1.9\" 170x320 или ESP32-S3-Touch-LCD)")
    elif "ESP-ROM:esp32c3" in log_text:
        chip_type = "ESP32-C3"
        hints.append("Обнаружен чип ESP32-C3 (часто мини-платы с круглым экраном 1.28\" GC9A01 или 0.42\" OLED)")
    elif "rst:0x" in log_text and "boot:0x" in log_text:
        chip_type = "ESP32 (классический двухъядерный Xtensa LX6)"
        hints.append("Обнаружен классический чип ESP32 (ESP32-2432S028 CYD 2.8\", TTGO T-Display 1.14\" или ESP32+OLED)")

    if re.search(r"PSRAM|spiram|Octal Flash", log_text, re.IGNORECASE):
        hints.append("В логе упоминается PSRAM (внешняя оперативная память — типично для T-Display S3 и камер/экранов)")

    if re.search(r"ILI9341|XPT2046|2432S028|lvgl", log_text, re.IGNORECASE):
        hints.append("В заводской прошивке найдены следы экрана ILI9341 / LVGL -> скорее всего это ESP32-2432S028 (CYD 2.8\")!")
    elif re.search(r"ST7789|TFT_eSPI|TTGO|LilyGO", log_text, re.IGNORECASE):
        hints.append("В заводской прошивке найдены следы ST7789 / LilyGO -> скорее всего это TTGO T-Display!")
    elif re.search(r"SSD1306|OLED|u8g2", log_text, re.IGNORECASE):
        hints.append("В заводской прошивке найдены следы OLED SSD1306 128x64!")

    return chip_type, hints


def capture_boot_log(port_name: str, baudrate: int = 115200, duration: float = 2.5) -> str:
    """Открывает порт, делает аппаратный сброс ESP32 через RTS/DTR и собирает загрузочный лог."""
    print(f"\n🔄 Читаем загрузочный лог с порта {port_name} ({baudrate} бод)...")
    try:
        with serial.Serial(port_name, baudrate, timeout=0.1) as ser:
            # Сброс платы через RTS/DTR
            ser.dtr = False
            ser.rts = True
            time.sleep(0.12)
            ser.rts = False
            ser.dtr = False

            start = time.time()
            chunks = []
            while time.time() - start < duration:
                data = ser.read(512)
                if data:
                    chunks.append(data.decode("utf-8", errors="replace"))
            return "".join(chunks)
    except Exception as e:
        print(f"⚠️ Не удалось прочитать порт {port_name}: {e}")
        return ""


def run_esptool_flash_id(port_name: str):
    """Запускает esptool flash_id, если установлен esptool."""
    print(f"\n🔬 Запрашиваем точную модель чипа и размер памяти через esptool ({port_name})...")
    for cmd in [
        [sys.executable, "-m", "esptool", "--port", port_name, "flash_id"],
        ["esptool.py", "--port", port_name, "flash_id"],
    ]:
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
            output = (res.stdout or "") + "\n" + (res.stderr or "")
            if "Detecting chip type" in output or "Chip is" in output:
                for line in output.splitlines():
                    if any(
                        k in line
                        for k in [
                            "Chip is",
                            "Features:",
                            "Crystal is",
                            "MAC:",
                            "Detected flash size:",
                            "Manufacturer:",
                        ]
                    ):
                        print("   ✅ " + line.strip())
                return output
        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"   ⚠️ esptool завершился с ошибкой: {e}")
            break
    print("   ℹ️ Модуль esptool не найден (можно установить: pip install esptool)")
    return ""


def main():
    print("=" * 68)
    print("🔍 СКАНЕР ПЛАТЫ ESP32 С ЭКРАНОМ (Определение модели по USB)")
    print("=" * 68)

    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("\n❌ COM/USB-порты не найдены!")
        print("Проверьте:")
        print("  1. Подключена ли плата к компьютеру кабелем с поддержкой передачи данных")
        print("     (некоторые кабели от зарядок имеют только 2 провода питания без данных!).")
        print("  2. Загорается ли светодиод или экран на плате.")
        sys.exit(0)

    print(f"\nНайдено последовательных портов: {len(ports)}\n")
    candidate_ports = []

    for idx, p in enumerate(ports, 1):
        vid_pid = (p.vid, p.pid) if p.vid and p.pid else None
        bridge_desc = KNOWN_USB_BRIDGES.get(vid_pid, "Неизвестный USB-UART мост или системный порт")
        vid_pid_str = f"VID:PID = {p.vid:04X}:{p.pid:04X}" if vid_pid else "без USB VID/PID"

        print(f"[{idx}] Порт: {p.device}")
        print(f"    Описание ОС : {p.description}")
        print(f"    USB ID      : {vid_pid_str}")
        print(f"    Чип связи   : {bridge_desc}")

        if vid_pid or "USB" in p.description.upper() or "UART" in p.description.upper() or "CP210" in p.description.upper() or "CH340" in p.description.upper():
            candidate_ports.append(p)

    target_ports = candidate_ports if candidate_ports else ports

    for p in target_ports:
        print("\n" + "-" * 68)
        print(f"🚀 Проверяем устройство на порту {p.device}...")
        boot_log = capture_boot_log(p.device, 115200)
        if boot_log.strip():
            print("📜 Получен лог запуска платы (первые 600 символов):")
            print("-" * 40)
            print(boot_log.strip()[:600])
            print("-" * 40)
            chip_type, hints = analyze_boot_log(boot_log)
            if hints:
                print("\n💡 Выводы по загрузочному логу:")
                for h in hints:
                    print(f"   • {h}")
        else:
            print("ℹ️ Лог на скорости 115200 пуст (возможно, это ESP8266 на 74880 бод или плата ждёт сброса).")

        esptool_out = run_esptool_flash_id(p.device)

        print("\n📌 ЧТО ДЕЛАТЬ ДАЛЬШЕ:")
        if p.vid == 0x1A86 and p.pid == 0x7523:
            print("   У вас чип CH340. Если плата ЖЁЛТОГО цвета с экраном 2.8\" — это 100% ESP32-2432S028 (CYD)!")
            print("   Если это маленький кубик с экраном — это GeekMagic SmallTV.")
        elif p.vid == 0x303A:
            print("   У вас современная плата со встроенным USB (ESP32-S3 или ESP32-C3), например LilyGO T-Display-S3.")
        elif p.vid == 0x10C4 or (p.vid == 0x1A86 and p.pid == 0x55D4):
            print("   У вас чип CP2102/CH9102 — чаще всего это LilyGO TTGO T-Display 1.14\", ESP32 с OLED 0.96\" или CYD Type-C.")
        print("   👉 Откройте диагностический веб-интерфейс или пришлите вывод этого скрипта (или фото платы) в чат!")


if __name__ == "__main__":
    main()
