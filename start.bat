@echo off
chcp 65001 >nul
echo 🚀 Запуск сайта установки часов и календарей для ESP32-2432S028...
start http://localhost:3000
node server.js
pause
