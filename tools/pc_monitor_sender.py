#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт отправки параметров компьютера (CPU, RAM, GPU, Диск, Сеть, Время) на виджет ESP32.
Работает по USB (Serial) и не требует сложной настройки!

Установка зависимостей:
    pip install psutil pyserial

Запуск:
    python pc_monitor_sender.py
    или с указанием порта:
    python pc_monitor_sender.py --port COM3
"""

import argparse
import json
import time
import sys
from datetime import datetime

try:
    import psutil
except ImportError:
    print("❌ Не установлена библиотека psutil. Установите: pip install psutil pyserial")
    sys.exit(1)

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("❌ Не установлена библиотека pyserial. Установите: pip install psutil pyserial")
    sys.exit(1)


def find_esp32_port():
    """Автоматически ищет USB COM-порт платы ESP32."""
    ports = list(serial.tools.list_ports.comports())
    esp_vids = {0x10C4, 0x1A86, 0x303A, 0x0403}
    for p in ports:
        if p.vid in esp_vids:
            return p.device
    for p in ports:
        desc = (p.description or "").upper()
        if any(k in desc for k in ("USB", "UART", "CP210", "CH340", "CH9102", "SERIAL")):
            return p.device
    return ports[0].device if ports else None


def get_cpu_temp():
    """Пытается прочитать температуру процессора (если доступно в ОС)."""
    try:
        if hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures()
            for name in ("coretemp", "k10temp", "cpu_thermal", "acpitz"):
                if name in temps and temps[name]:
                    return int(round(temps[name][0].current))
            for entries in temps.values():
                if entries:
                    return int(round(entries[0].current))
    except Exception:
        pass
    return 0


def collect_pc_metrics(prev_net):
    """Собирает метрики системы в компактный JSON-пакет для ESP32."""
    cpu = int(round(psutil.cpu_percent(interval=None)))
    mem = psutil.virtual_memory()
    ram = int(round(mem.percent))
    ram_used_gb = round(mem.used / (1024 ** 3), 1)
    ram_total_gb = round(mem.total / (1024 ** 3), 1)

    try:
        disk = int(round(psutil.disk_usage("/").percent))
    except Exception:
        disk = 0

    now_net = psutil.net_io_counters()
    dt = max(0.2, time.time() - prev_net["t"])
    down_kbps = int(round((now_net.bytes_recv - prev_net["rx"]) / 1024.0 / dt))
    up_kbps = int(round((now_net.bytes_sent - prev_net["tx"]) / 1024.0 / dt))
    prev_net["rx"] = now_net.bytes_recv
    prev_net["tx"] = now_net.bytes_sent
    prev_net["t"] = time.time()

    now = datetime.now()
    payload = {
        "cmd": "pc",
        "cpu": cpu,
        "ram": ram,
        "ram_gb": f"{ram_used_gb}/{ram_total_gb}G",
        "temp": get_cpu_temp(),
        "disk": disk,
        "down": down_kbps,
        "up": up_kbps,
        "time": now.strftime("%H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "year": now.year,
        "month": now.month,
        "day": now.day,
        "wday": now.isoweekday(),  # 1 = Пн ... 7 = Вс
    }
    return payload


def main():
    parser = argparse.ArgumentParser(description="Отправка мониторинга ПК на ESP32 по USB")
    parser.add_argument("--port", help="COM-порт ESP32 (например COM3 или /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=115200, help="Скорость порта (по умолчанию 115200)")
    parser.add_argument("--interval", type=float, default=1.0, help="Интервал обновления в секундах")
    args = parser.parse_args()

    port = args.port or find_esp32_port()
    if not port:
        print("❌ Не найден COM-порт ESP32! Подключите плату по USB или укажите --port COMx")
        sys.exit(1)

    print(f"🔌 Подключение к ESP32 на порту {port} ({args.baud} бод)...")
    psutil.cpu_percent(interval=None)
    net0 = psutil.net_io_counters()
    prev_net = {"rx": net0.bytes_recv, "tx": net0.bytes_sent, "t": time.time()}

    try:
        with serial.Serial(port, args.baud, timeout=0.2) as ser:
            print("✅ Подключено! Отправляем данные CPU / RAM / Сети / Времени (Ctrl+C для выхода)...")
            while True:
                pkt = collect_pc_metrics(prev_net)
                line = json.dumps(pkt, ensure_ascii=False) + "\n"
                ser.write(line.encode("utf-8"))
                print(
                    f"\r📊 CPU: {pkt['cpu']:3d}% | RAM: {pkt['ram']:3d}% ({pkt['ram_gb']}) | "
                    f"Down: {pkt['down']:4d} KB/s | 🕒 {pkt['time']}   ",
                    end="",
                    flush=True,
                )
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n👋 Остановлено пользователем.")
    except Exception as e:
        print(f"\n❌ Ошибка связи с портом {port}: {e}")


if __name__ == "__main__":
    main()
