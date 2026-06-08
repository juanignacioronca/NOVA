#!/bin/bash
# NOVA — doctor de proveedores (doble clic, sin terminal).
# Primera vez en macOS: clic derecho → Abrir (Gatekeeper bloquea el doble clic inicial).
#
# Usa el intérprete donde hiciste `pip install -e .` (python3 por defecto;
# overrideable con NOVA_PYTHON). cd a la raíz del repo sin rutas absolutas.

cd "$(dirname "$0")" || exit 1
PY="${NOVA_PYTHON:-python3}"

"$PY" -m nova.doctor

echo
read -r -p "Enter para cerrar esta ventana…" _
