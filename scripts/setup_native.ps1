# NOVA — setup NATIVO (una sola vez). Crea el venv, instala dependencias y
# compila el frontend. Reejecutable sin romper nada.
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\setup_native.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# 1) Python (busca el 3.12 instalado por winget; si no, avisa)
$py = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
if (-not (Test-Path $py)) {
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Source -notmatch "WindowsApps") { $py = $cmd.Source }
  else { throw "No encuentro Python 3.12. Instalalo: winget install Python.Python.3.12" }
}
Write-Host "[setup] Python: $py"

# 2) venv
if (-not (Test-Path "$root\.venv\Scripts\python.exe")) {
  Write-Host "[setup] creando venv…"; & $py -m venv "$root\.venv"
}
$venv = "$root\.venv\Scripts\python.exe"
& $venv -m pip install --upgrade pip
& $venv -m pip install -e "$root[dev,server,memory]" "ruamel.yaml"

# 3) frontend
Write-Host "[setup] compilando frontend…"
Push-Location "$root\frontend"
if (-not (Test-Path "node_modules")) { npm install }
npm run build
Pop-Location

Write-Host "[setup] LISTO. Arrancá con:  scripts\start_nova.ps1   (o start_nova.bat)"
