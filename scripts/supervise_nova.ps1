# NOVA — supervisor (arranque + auto-update por git). Pensado para Task Scheduler
# al iniciar sesión: mantiene NOVA viva y, cuando hay cambios en GitHub (que
# pusheás desde la Mac), hace `git pull`, recompila lo necesario y reinicia.
#
# Uso (manual): powershell -ExecutionPolicy Bypass -File scripts\supervise_nova.ps1
# Registrar como autostart: scripts\install_autostart.ps1
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = Join-Path $root ".venv\Scripts\python.exe"
$proc = $null

function Start-Nova {
  $env:NOVA_HOST = "0.0.0.0"; $env:NOVA_PORT = "8000"; $env:OLLAMA_KEEP_ALIVE = "-1"
  if (-not $env:OLLAMA_HOST) { $env:OLLAMA_HOST = "http://localhost:11434" }
  try {
    $b = '{"model":"llama3.2:3b","prompt":"hola","stream":false,"keep_alive":-1}'
    Invoke-RestMethod -Uri "$($env:OLLAMA_HOST)/api/generate" -Method Post -Body $b -TimeoutSec 90 | Out-Null
  } catch {}
  Write-Host "[supervise] arrancando NOVA…"
  return Start-Process -FilePath $py -ArgumentList @("-m","uvicorn","nova.app:app","--host","0.0.0.0","--port","8000") -PassThru -WindowStyle Hidden
}

function Stop-Nova {
  if ($proc -and -not $proc.HasExited) { try { Stop-Process -Id $proc.Id -Force } catch {} }
  # por si quedó algo escuchando en 8000
  $c = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
  if ($c) { $c | Select-Object -Expand OwningProcess -Unique | ForEach-Object { try { Stop-Process -Id $_ -Force } catch {} } }
}

while ($true) {
  # --- auto-update desde GitHub ---
  try {
    git fetch origin main 2>$null
    $local = (git rev-parse HEAD).Trim()
    $remote = (git rev-parse origin/main).Trim()
    if ($local -and $remote -and ($local -ne $remote)) {
      $changed = (git diff --name-only HEAD origin/main) -join "`n"
      Write-Host "[supervise] cambios en GitHub → actualizando…"
      $pull = git pull --ff-only 2>&1
      if ($LASTEXITCODE -eq 0) {
        if ($changed -match "pyproject\.toml") { & $py -m pip install -e "$root[dev,server,memory]" "ruamel.yaml" }
        if ($changed -match "(^|`n)frontend/") {
          Push-Location "$root\frontend"; if (-not (Test-Path node_modules)) { npm install }; npm run build; Pop-Location
        }
        Stop-Nova; $proc = $null
      } else {
        Write-Host "[supervise] pull no fast-forward (hay cambios locales). Salteo. $pull"
      }
    }
  } catch { Write-Host "[supervise] aviso update: $_" }

  # --- mantener viva ---
  if (-not $proc -or $proc.HasExited) { $proc = Start-Nova }
  Start-Sleep -Seconds 60
}
