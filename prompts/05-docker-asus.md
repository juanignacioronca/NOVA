# Prompt 5 — Docker + despliegue en el ASUS

> Pega todo lo que está **bajo la línea** en Claude Code, en el repo de NOVA (Prompts 1–4 andando, Python 3.12). Esta fase empaqueta NOVA para correr **24/7 en el ASUS** (la máquina dedicada con GPU). Claude Code crea los artefactos y los **valida localmente** (build + smoke test en CPU); el despliegue real lo corro yo en el ASUS siguiendo el README. Mantén async, Registry, bóveda de secretos.

---

Lee `CLAUDE.md`. NOVA pasa de script a **servicio**: un backend alcanzable en la red, empaquetado en Docker junto a Ollama, seguro por defecto.

## Objetivo
- NOVA corre 24/7 en el ASUS con `docker compose up -d`, con **Ollama** (modelos locales, GPU) en el mismo compose.
- Es **alcanzable desde la LAN**: desde el navegador del teléfono/iPad/Mac le puedo hablar por una página mínima (sin frontend aún).
- **Seguro por defecto:** sin puertos expuestos a internet, claves fuera de la imagen, contenedor sin root, política de reinicio.
- En el Mac, Claude Code valida que la imagen **buildea y arranca** (CPU, percepción off) con un smoke test.

## Construye

1. **Servicio NOVA** (`app.py`, FastAPI + WebSocket):
   - Envuelve el Conductor: `POST /chat` (texto → respuesta), `WebSocket /ws` que streamea la traza/eventos en vivo (reusa el stream de `TraceEvent` del Prompt 3) + la respuesta, y `GET /health`.
   - `GET /` = página mínima (HTML/JS inline, sin dependencias): un input, área de respuesta y la traza en vivo por WS. Para hablarle desde el navegador del teléfono ya. (El PWA lindo es Prompt 7.)
   - Bind configurable; por defecto a la LAN, **nunca** pensado para WAN.

2. **Dockerfile:**
   - Base `python:3.12-slim`, multi-stage (build deps → runtime liviano). Usuario **no-root**.
   - Instala el paquete (`pip install .`), copia solo lo necesario. `EXPOSE` el puerto del servicio. `HEALTHCHECK` contra `/health`.
   - **No** incluyas `.env` ni claves (van por runtime).

3. **`.dockerignore`:** excluye `.venv`, `.env`, `logs/`, `__pycache__`, datos de tests, etc.

4. **`docker-compose.yml`:**
   - Servicio `nova` (build local) + `ollama` (imagen `ollama/ollama`).
   - `nova` depende de `ollama`; `OLLAMA_HOST=http://ollama:11434`.
   - **Volúmenes:** modelos de Ollama (persistentes), `logs/`, y el `.env` por `env_file`/montaje en runtime.
   - `restart: unless-stopped`. Límites de recursos. Red interna; **solo** el puerto de `nova` publicado y **atado a la LAN** (no `0.0.0.0` público). Ollama **no** se publica (solo red interna).
   - Percepción **off por defecto** en el contenedor (un servidor headless no tiene mic/cámara). Documenta cómo activarla si el ASUS tiene cámara/mic (device passthrough `/dev/video0`, audio) como **opción avanzada**.

5. **Override de GPU** (`docker-compose.gpu.yml`):
   - Habilita NVIDIA para `ollama` vía NVIDIA Container Toolkit (`gpus: all` / `deploy.resources.reservations.devices`).

6. **Despliegue** (`deploy/README.md` + `deploy/up.sh`):
   - Pasos para el ASUS: instalar Docker (+ NVIDIA Container Toolkit si hay GPU), `git pull`, crear `.env`, `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d`, y `docker exec ollama ollama pull qwen2.5:7b qwen2.5vl:7b llama3.2:3b`.
   - Cubre **Linux** (recomendado) y deja una nota para **Windows + WSL2** (Docker Desktop + WSL2 + GPU).
   - **Seguridad:** el puerto solo en la LAN; para acceso remoto fuera de casa **NO abrir puertos** — eso se hace con Tailscale en el Prompt 7.

7. **Hardening** (buenas prácticas tipo OpenClaw, concretadas):
   - Contenedor **no-root**; filesystem read-only donde se pueda; `cap_drop`; sin host network.
   - Claves solo por `.env`/secrets en runtime, **jamás** en la imagen ni en logs.
   - Servicio atado a la LAN; documenta explícito "no exponer a internet".
   - Actualiza `CLAUDE.md` §11 con el modelo de despliegue seguro.

8. **Validación local (Mac — lo que SÍ puedes hacer acá):**
   - `docker build` (arm64) + `docker run` CPU-only, percepción off → smoke test: `GET /health` OK, `POST /chat "hola"` responde (stub/local), `GET /` carga.
   - Si no tengo Docker instalado en el Mac, crea igual todos los artefactos y deja el smoke test como script (`deploy/smoke.sh`) para cuando lo instale.
   - **Nota clara:** la imagen real del ASUS se **buildea en el ASUS** (x86_64 + GPU); el build del Mac es solo validación del Dockerfile.

9. **Tests** (offline): `/health` y `/chat` (Conductor en stub) responden; `app.py` levanta. `pytest` verde.

## Reglas
- Sin secretos en la imagen ni en logs. Servicio a la **LAN, nunca WAN**.
- Contenedor no-root, mínimos privilegios. Respeta Registry/interfaces/bóveda de secretos.

## No hagas todavía
- Acceso remoto fuera de casa (Tailscale) y el frontend/PWA lindo → **Prompt 7**.
- Capturar mic/cámara dentro del contenedor → solo como opción avanzada documentada; la solución limpia (captura en el dispositivo, cómputo en el ASUS) es del Prompt 7.

## Criterio de aceptación
- En el Mac: la imagen buildea y arranca CPU-only; `/health`, `/chat` y `/` responden; smoke test OK; `pytest` verde.
- Existen `Dockerfile`, `.dockerignore`, compose base + override GPU, y `deploy/README.md` con pasos para el ASUS (Linux + nota WSL2) y la advertencia de no exponer a internet.
- Actualiza `CLAUDE.md` §10 (Prompt 5 completo) y §11 (despliegue seguro). Nota qué sigue → **Prompt 6 (Herramientas)**.
