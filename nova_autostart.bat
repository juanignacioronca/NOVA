@echo off
:: NOVA Autostart NATIVO — levanta el supervisor (NOVA viva + auto-update git).
:: (Reemplaza el viejo autostart por Docker.) Lo ideal es registrarlo como tarea
:: programada con scripts\install_autostart.ps1; este .bat sirve para correrlo a mano.
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File "%~dp0scripts\supervise_nova.ps1"
