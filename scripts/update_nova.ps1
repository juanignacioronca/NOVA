# NOVA — actualización manual (one-shot): trae lo último de GitHub, recompila lo
# necesario y reinicia. (El supervisor hace esto solo cada 60s; esto es para forzarlo.)
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\update_nova.ps1
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = Join-Path $root ".venv\Scripts\python.exe"

$changed = (git diff --name-only HEAD origin/main 2>$null) -join "`n"
git fetch origin main 2>$null
Write-Host "[update] git pull…"
git pull --ff-only
if ($LASTEXITCODE -ne 0) { Write-Host "[update] pull falló (¿cambios locales sin commitear?). Abortando."; exit 1 }

if ($changed -match "pyproject\.toml") {
  Write-Host "[update] dependencias cambiaron → pip install"
  & $py -m pip install -e "$root[dev,server,memory]" "ruamel.yaml"
}
if ($changed -match "(^|`n)frontend/") {
  Write-Host "[update] frontend cambió → npm run build"
  Push-Location "$root\frontend"; if (-not (Test-Path node_modules)) { npm install }; npm run build; Pop-Location
}

Write-Host "[update] reiniciando NOVA (el supervisor la vuelve a levantar)…"
$c = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($c) { $c | Select-Object -Expand OwningProcess -Unique | ForEach-Object { try { Stop-Process -Id $_ -Force } catch {} } }
Write-Host "[update] listo."
