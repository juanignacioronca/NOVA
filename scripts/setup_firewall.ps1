# NOVA — regla de firewall (CORRER COMO ADMINISTRADOR).
# Permite el puerto 8000 entrante SOLO desde la LAN y desde Tailscale (100.64.0.0/10),
# nunca desde una IP pública arbitraria. Acceso fuera de casa = Tailscale (ver REMOTE.md).
# Uso (PowerShell admin):  powershell -ExecutionPolicy Bypass -File scripts\setup_firewall.ps1
$ErrorActionPreference = "Stop"

$name = "NOVA 8000 (LAN + Tailscale)"
Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue | Remove-NetFirewallRule

New-NetFirewallRule `
  -DisplayName $name `
  -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 `
  -RemoteAddress @("192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12", "100.64.0.0/10") `
  -Profile Any | Out-Null

Write-Host "[firewall] Regla creada: puerto 8000 abierto a LAN + Tailscale (no a internet público)."
Write-Host "[firewall] Probá desde otro dispositivo de la red: http://$($env:NOVA_LAN_IP):8000  (o tu IP LAN)"
