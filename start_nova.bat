@echo off
:: NOVA — arranque nativo (doble clic). Abre el servidor en http://localhost:8000
:: y deja la ventana abierta. Para autostart al login usá scripts\install_autostart.ps1
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0scripts\start_nova.ps1"
pause
