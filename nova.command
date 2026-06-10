#!/bin/bash
# NOVA — daemon de percepción (audio + texto + video + avisos). Doble clic.
# Primera vez en macOS: clic derecho → Abrir (Gatekeeper). macOS pedirá permiso
# de micrófono y cámara la primera vez.
#
# Usa el venv del repo (.venv, Python 3.12) si existe; si no, NOVA_PYTHON/python3.

cd "$(dirname "$0")" || exit 1
if [ -x ".venv/bin/python" ]; then PY=".venv/bin/python"; else PY="${NOVA_PYTHON:-python3}"; fi

"$PY" -m nova.run

echo
read -r -p "Enter para cerrar esta ventana…" _
