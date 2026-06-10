#!/usr/bin/env bash
# Arranca NOVA en el ASUS. Uso:
#   ./deploy/up.sh           # CPU
#   ./deploy/up.sh --gpu     # con GPU NVIDIA (override gpu)
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Falta .env. Crealo:  cp .env.example .env  (y poné NOVA_LAN_IP=<ip-del-asus>)"
  exit 1
fi

if [ "${1:-}" = "--gpu" ]; then
  echo "==> up con GPU"
  docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
else
  echo "==> up (CPU)"
  docker compose up -d --build
fi

echo "==> pulleando modelos en Ollama (la 1ª vez tarda)"
docker exec ollama ollama pull qwen2.5:7b    || true
docker exec ollama ollama pull qwen2.5vl:7b  || true
docker exec ollama ollama pull llama3.2:3b   || true

docker compose ps
echo "Listo. NOVA en http://<NOVA_LAN_IP>:8000  (solo LAN)."
