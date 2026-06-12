# NOVA — registrar autostart NATIVO (CORRER COMO ADMINISTRADOR).
# Crea una tarea programada que, al iniciar sesión, levanta el supervisor
# (mantiene NOVA viva + auto-update por git). Reemplaza el viejo autostart de Docker.
# Uso (PowerShell admin):  powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\supervise_nova.ps1"

# Desactivar el autostart viejo de Docker si quedó registrado.
foreach ($old in @("NOVA Autostart", "NOVA-Docker", "nova_autostart")) {
  Get-ScheduledTask -TaskName $old -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false -ErrorAction SilentlyContinue
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -NoProfile -File `"$script`""
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName "NOVA" -Action $action -Trigger $trigger -Settings $settings `
  -RunLevel Highest -Description "NOVA: supervisor nativo (arranque + auto-update git)" -Force | Out-Null

Write-Host "[autostart] Tarea 'NOVA' registrada (arranca al iniciar sesión)."
Write-Host "[autostart] Iniciar ahora:  Start-ScheduledTask -TaskName NOVA"
