# NOVA — arranque NATIVO (Windows + venv + Ollama GPU).
# Escucha en 0.0.0.0:8000 → alcanzable en la LAN y por Tailscale.
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\start_nova.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "No existe el venv en $py. Corré scripts\setup_native.ps1 primero." }

$env:NOVA_HOST = "0.0.0.0"
$env:NOVA_PORT = "8000"
if (-not $env:OLLAMA_HOST) { $env:OLLAMA_HOST = "http://localhost:11434" }
# El modelo local queda cargado en GPU indefinidamente (primer turno rápido).
$env:OLLAMA_KEEP_ALIVE = "-1"

# Pre-cargar el modelo local en la GPU (keep_alive -1 = no se descarga).
try {
  $body = '{"model":"llama3.2:3b","prompt":"hola","stream":false,"keep_alive":-1}'
  Invoke-RestMethod -Uri "$($env:OLLAMA_HOST)/api/generate" -Method Post -Body $body -TimeoutSec 90 | Out-Null
  Write-Host "[NOVA] modelo local pre-cargado en GPU."
} catch { Write-Host "[NOVA] aviso: no pude pre-cargar el modelo (Ollama no responde?)." }

Write-Host "[NOVA] arrancando en http://0.0.0.0:8000  (LAN: http://$($env:NOVA_LAN_IP):8000)"
& $py -m uvicorn nova.app:app --host 0.0.0.0 --port 8000 --log-level info
