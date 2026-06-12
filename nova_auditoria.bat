@echo off
:: Auditoria semanal de NOVA — ejecutado por Task Scheduler cada lunes.
:: Guarda reporte en C:\nova\auditoria\reportes\YYYY-MM-DD.md

set FECHA=%DATE:~6,4%-%DATE:~3,2%-%DATE:~0,2%
set REPORTES=C:\nova\auditoria\reportes
if not exist "%REPORTES%" mkdir "%REPORTES%"
set REPORTE=%REPORTES%\%FECHA%.md

echo # Auditoria NOVA — %FECHA% > "%REPORTE%"
echo. >> "%REPORTE%"

:: 1. Estado del container
echo ## Estado Docker >> "%REPORTE%"
echo ```>> "%REPORTE%"
docker compose -f C:\nova\docker-compose.nova-only.yml ps >> "%REPORTE%" 2>&1
echo ```>> "%REPORTE%"
echo. >> "%REPORTE%"

:: 2. Health check
echo ## Health >> "%REPORTE%"
echo ```>> "%REPORTE%"
curl -s http://192.168.4.30:8000/health >> "%REPORTE%" 2>&1
echo. >> "%REPORTE%"
echo ```>> "%REPORTE%"
echo. >> "%REPORTE%"

:: 3. Test chat
echo ## Smoke test /chat >> "%REPORTE%"
echo ```>> "%REPORTE%"
curl -s -X POST http://192.168.4.30:8000/chat -H "Content-Type: application/json" -d "{\"text\":\"estado del sistema\"}" >> "%REPORTE%" 2>&1
echo. >> "%REPORTE%"
echo ```>> "%REPORTE%"
echo. >> "%REPORTE%"

:: 4. Modelos Ollama
echo ## Modelos Ollama >> "%REPORTE%"
echo ```>> "%REPORTE%"
curl -s http://localhost:11434/api/tags >> "%REPORTE%" 2>&1
echo. >> "%REPORTE%"
echo ```>> "%REPORTE%"
echo. >> "%REPORTE%"

:: 5. Espacio en disco
echo ## Disco >> "%REPORTE%"
echo ```>> "%REPORTE%"
wmic logicaldisk where "DeviceID='C:'" get Size,FreeSpace,Caption /format:list >> "%REPORTE%" 2>&1
echo ```>> "%REPORTE%"
echo. >> "%REPORTE%"

:: 6. Logs recientes (ultimas 20 lineas)
echo ## Logs recientes >> "%REPORTE%"
echo ```>> "%REPORTE%"
docker compose -f C:\nova\docker-compose.nova-only.yml logs --tail=20 nova >> "%REPORTE%" 2>&1
echo ```>> "%REPORTE%"

echo Auditoria guardada en: %REPORTE%
