# Desplegar NOVA en el ASUS (24/7)

NOVA como servicio en Docker, junto a Ollama (modelos locales con GPU). Seguro por
defecto: **solo LAN, nunca internet**, claves fuera de la imagen, contenedor no-root.

> La imagen real se **buildea en el ASUS** (x86_64 + GPU). El build en el Mac
> (arm64) es solo validación del Dockerfile (`deploy/smoke.sh`).

---

## 1. Requisitos en el ASUS

### Linux (recomendado)
1. **Docker Engine + Compose v2**
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker "$USER"   # re-logueá después
   ```
2. **GPU NVIDIA** (opcional pero recomendado para Ollama): **NVIDIA Container Toolkit**
   ```bash
   # https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html
   sudo apt-get install -y nvidia-container-toolkit
   sudo nvidia-ctk runtime configure --runtime=docker
   sudo systemctl restart docker
   docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi  # verificación
   ```

### Windows + WSL2 (alternativa)
- Instalá **Docker Desktop** con backend **WSL2**.
- Para GPU: drivers NVIDIA en Windows + “WSL GPU”; Docker Desktop expone `--gpus all` vía WSL2.
- Corré los comandos de abajo **dentro de la distro WSL2** (Ubuntu), con el repo clonado en el filesystem de Linux (`~/...`, no `/mnt/c`, por performance).

---

## 2. Traer el código y configurar

```bash
git clone <repo> nova && cd nova
git pull                      # si ya estaba clonado
cp .env.example .env
```

Editá `.env`:
- `NOVA_LAN_IP=<ip-del-asus>` (ej. `192.168.1.50`) → publica el puerto **solo** en la LAN.
  Si lo dejás vacío/`127.0.0.1`, NOVA solo se ve desde el propio ASUS.
- Claves de nube (opcionales): `GEMINI_API_KEY`, `GROQ_API_KEY`, etc. Sin ellas, NOVA usa local/stub.
- **No** pongas `OLLAMA_HOST` (lo setea el compose a `http://ollama:11434`).

---

## 3. Arrancar

```bash
./deploy/up.sh --gpu     # con GPU NVIDIA
# o:
./deploy/up.sh           # CPU
```

Esto hace `docker compose up -d --build` y pullea los modelos en Ollama
(`qwen2.5:7b`, `qwen2.5vl:7b`, `llama3.2:3b`). Manual, si preferís:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
docker exec ollama ollama pull qwen2.5:7b
docker exec ollama ollama pull qwen2.5vl:7b
docker exec ollama ollama pull llama3.2:3b
```

---

## 4. Usar

Desde cualquier dispositivo en la **misma red** (teléfono/iPad/Mac):

```
http://<NOVA_LAN_IP>:8000/
```

Página mínima para hablarle por texto (la traza en vivo va por WebSocket). API:
`GET /health`, `POST /chat {"text": "..."}`, `WS /ws`.

```bash
curl http://<NOVA_LAN_IP>:8000/health
curl -X POST http://<NOVA_LAN_IP>:8000/chat -H 'content-type: application/json' -d '{"text":"hola"}'
```

Operación:
```bash
docker compose ps
docker compose logs -f nova
docker compose down          # parar
```

---

## 5. Seguridad (importante)

- **Solo LAN.** El puerto se ata a `NOVA_LAN_IP`; Ollama **no** se publica (red interna).
- **NUNCA abras puertos del router a internet.** Para acceso remoto fuera de casa se usa
  **Tailscale** (Prompt 7), que crea una red privada sin exponer nada al WAN.
- **Claves** solo por `.env` en runtime; nunca en la imagen ni en logs.
- Contenedor **no-root**, `read_only`, `cap_drop: ALL`, `no-new-privileges`, sin host network.
- `restart: unless-stopped` → vuelve solo tras reinicios/caídas (24/7).

---

## 6. Validación local (Mac, sin GPU)

```bash
./deploy/smoke.sh     # build + run CPU-only + chequea /health, /chat, /
```

(La percepción —mic/cámara— está **off** en el contenedor: un servidor headless no
tiene esos dispositivos. Captura en el dispositivo + cómputo en el ASUS = Prompt 7.)
