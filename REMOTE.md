# NOVA — acceso desde otros dispositivos (LAN y fuera de casa)

NOVA corre **nativa** en el ASUS (Python + venv + Ollama con GPU) y escucha en
`0.0.0.0:8000`. Desde el navegador vas a ver la esfera, hablarle por voz, la
cámara y el modo configuración.

## 1. En la misma casa (LAN) — listo ya

1. Abrí el firewall una vez (PowerShell **como administrador**):
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\setup_firewall.ps1
   ```
   Abre el puerto 8000 **solo** a la red local y a Tailscale (no a internet).

2. Desde cualquier dispositivo de tu red (Mac, teléfono, iPad), entrá a:
   ```
   http://192.168.4.30:8000
   ```
   (esa es la IP del ASUS = `NOVA_LAN_IP` en `.env`; si cambia, mirá `ipconfig`).

## 2. Fuera de casa, con la PC en casa — Tailscale (recomendado)

Tailscale es una VPN privada: tus dispositivos se ven entre sí con una IP estable
`100.x.x.x`, **sin abrir puertos del router a internet** (seguro y simple). Es lo
ideal para la futura app de iPhone.

1. En el ASUS: instalá Tailscale y logueate.
   ```powershell
   winget install Tailscale.Tailscale
   tailscale up
   ```
2. En la Mac / iPhone: instalá Tailscale y logueate con **la misma cuenta**.
3. Mirá la IP de Tailscale del ASUS (empieza con `100.`):
   ```powershell
   tailscale ip -4
   ```
4. Desde afuera, entrás a NOVA en:
   ```
   http://100.x.x.x:8000
   ```
   Funciona estés donde estés, mientras el ASUS esté prendido.

> **Link bonito / HTTPS:** con `tailscale serve` o `tailscale funnel` podés exponer
> NOVA en una URL `https://asus.tu-tailnet.ts.net`. Funnel la hace accesible incluso
> sin Tailscale en el cliente (útil para una webapp/PWA pública) — pero eso ya es
> exponer a internet: activalo solo cuando quieras y con conciencia del riesgo.

## 3. App de iPhone (futuro)

La interfaz web ya es responsive y usa el micrófono/cámara del navegador. Para una
app nativa o PWA, apuntá al backend por su IP de Tailscale (`http://100.x.x.x:8000`)
o a la URL de `tailscale funnel`. El contrato es el mismo WebSocket `/ws` + `/tts`.

## Seguridad (resumen)

- El puerto 8000 se abre **solo** a rangos privados + Tailscale (`setup_firewall.ps1`).
- **No** hagas port-forwarding del router a internet. Si necesitás un link público,
  usá `tailscale funnel` (cifrado, con identidad) en vez de abrir el router.
- Las claves de IA viven solo en `.env` (no se commitea). Cara/voz/memoria son locales.
