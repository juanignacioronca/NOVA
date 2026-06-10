#!/usr/bin/env bash
# Validación local (Mac u otro): la imagen buildea y arranca CPU-only (percepción
# off, sin Ollama → cae a stub/local) y responde /health, /chat y /.
# OJO: en el Mac (arm64) el build es solo validación del Dockerfile; la imagen
# real del ASUS se buildea en el ASUS (x86_64 + GPU).
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE=nova:smoke
NAME=nova-smoke
PORT=8000

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker no está instalado. Instalalo y volvé a correr este script."
  exit 1
fi

echo "==> docker build"
docker build -t "$IMAGE" .

echo "==> docker run (CPU-only, Ollama inalcanzable a propósito → stub/local)"
docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" \
  -e OLLAMA_HOST=http://127.0.0.1:9 \
  -p 127.0.0.1:${PORT}:8000 "$IMAGE" >/dev/null
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "==> esperando /health…"
ok=
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then ok=1; break; fi
  sleep 1
done
if [ -z "$ok" ]; then echo "FALLO: /health no respondió"; docker logs "$NAME"; exit 1; fi
echo "   /health: $(curl -fsS http://127.0.0.1:${PORT}/health)"

echo "==> POST /chat"
curl -fsS -X POST "http://127.0.0.1:${PORT}/chat" \
  -H 'content-type: application/json' -d '{"text":"hola"}'
echo

echo "==> GET /"
curl -fsS "http://127.0.0.1:${PORT}/" | grep -q NOVA && echo "   / cargó la página"

echo "SMOKE OK ✅"
