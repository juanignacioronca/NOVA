# NOVA — HANDOFF (cómo operar NOVA)

Esto es NOVA y así se opera. Asistente personal multiagente, **local-first, $0**,
con un único **Conductor** que entiende, orquesta y responde. La fuente de verdad
del diseño es [CLAUDE.md](CLAUDE.md); este doc es la guía de operación.

---

## 1. Qué hay (capacidades)

- **Conductor real**: comprende (modelo + heurística), clasifica simple/complejo, pregunta si falta info, sintetiza. Multimodal (imágenes).
- **Grupo Local** (Ollama, $0): respuestas rápidas, Sentinela (visión), memoria de trabajo.
- **Empresa / Grupo Nube** (free-tier): PMO descompone y reparte a áreas; transversales Finanzas/Estrategia cruzan; **data-driven** desde `config/teams.yaml`.
- **Herramientas**: clima, web, lugares, calendario, recordatorios/timer, correo (gated). Allowlist + permisos + confirmación + contenido externo no confiable.
- **Percepción** (Prompt 4): loop audio + texto + video, modo Sentinela, **avisos proactivos**.
- **Memoria** (Prompt 8): grafo + vectores (SQLite local) + bóveda **Obsidian**.
- **Reconocimiento** (Prompt 10): cara + voz por embeddings, enrolados en la memoria, **100% local**.
- **Salidas + visual** (Prompt 9): backend FastAPI/WS + frontend Three.js (NOVA audio-reactiva, flujo en vivo, pantalla dinámica, modalidad).

---

## 2. Entorno (una vez)

```bash
# Python 3.11+ (acá usamos el de Homebrew) + venv del repo
/opt/homebrew/bin/python3.12 -m venv .venv && source .venv/bin/activate

pip install -e ".[dev]"            # núcleo (texto) + tests
pip install -e ".[server]"         # backend web (FastAPI/WS)
pip install -e ".[memory]"         # memoria (numpy + networkx)
# Opcionales (hardware/modelos reales):
pip install -e ".[perception]"     # audio/video/voz (antes: brew install portaudio ffmpeg)
pip install -e ".[recognition]"    # cara/voz (insightface/onnxruntime, resemblyzer)

cp .env.example .env               # opcional: claves de nube (sin ellas → local/stub)
```

Modelos locales (Ollama): `ollama pull qwen2.5:7b qwen2.5vl:7b llama3.2:3b nomic-embed-text`.
Voz Piper: dejá un `.onnx` en `~/.local/share/piper/` (o `NOVA_PIPER_DIR`).

---

## 3. Correr cada cosa

| Quiero… | Comando |
|---|---|
| Probar por texto (rápido) | `python -m nova.chat` |
| Ver estado de proveedores | `python -m nova.doctor` |
| Backend web (API + WS) | `python -m nova.app` → `http://<host>:8000/` |
| Frontend visual (dev) | `cd frontend && npm install && npm run dev` → `:5173` |
| Frontend visual (prod) | `cd frontend && npm run build` → servir `dist/` estático |
| Daemon de percepción | `python -m nova.run` (o doble clic `nova.command`) |
| Enrolar una persona | `python -m nova.enroll <nombre> --fotos <carpeta> [--voz <carpeta>]` |
| Borrar biométricos | `python -m nova.enroll <nombre> --borrar` |
| Smoke end-to-end | `python scripts/smoke_e2e.py` |
| Tests | `pytest` (offline; sin red ni modelos) |

Sin claves ni Ollama, NOVA corre en **modo stub** (determinista) — todo enlaza igual.

---

## 4. Enrolar personas (cara/voz)

```bash
# Convención: personas/<nombre>/fotos/  y  personas/<nombre>/voz/
python -m nova.enroll Juan --fotos personas/Juan/fotos --voz personas/Juan/voz
```

5–20 fotos / unas muestras de voz alcanzan. Los vectores quedan en el **nodo de la
persona en la memoria** (local). Al runtime, el Sentinela matchea la cara y el Oído
la voz; si la persona tiene pendientes, el proactivo avisa: *"se acerca Juan;
probablemente por: …"*. Para olvidar a alguien: `--borrar`.

---

## 5. Desplegar en el ASUS (24/7)

Artefactos en el repo (Prompt 5): `Dockerfile`, `docker-compose.yml`,
`docker-compose.gpu.yml`, `deploy/`. Pasos completos en
[deploy/README.md](deploy/README.md). Resumen:

```bash
git pull && cp .env.example .env       # poné NOVA_LAN_IP=<ip-del-asus>
./deploy/up.sh --gpu                    # compose + pull de modelos en Ollama
# navegás a http://<NOVA_LAN_IP>:8000/ desde el teléfono (misma red)
```

> La **imagen real se buildea en el ASUS** (x86_64 + GPU). En el Mac (arm64) el
> build es solo validación del Dockerfile (`deploy/smoke.sh`).

---

## 6. Estrategia de modelos ($0)

Mapa agente→modelo en `config/models.yaml` (fuente de verdad):
- **Lo que corre mucho/siempre → local** (Ollama): conductor simple, respuestas rápidas, memoria, Sentinela, cálculos.
- **Lo complejo/poco frecuente → nube free-tier** repartido: líderes/redactores → **Gemini Flash**; investigadores → **Groq Llama 3.3 70B**; razonamiento pesado → **DeepSeek R1** (OpenRouter).
- **Opus** solo donde rinde: la **auditoría** (asíncrona). Resiliencia: 429/5xx → backoff → fallback local → stub.

---

## 7. Seguridad y privacidad (resumen; detalle en CLAUDE.md §11)

- **Anti-inyección estructural**: instrucciones de NOVA solo en `system`; usuario/externo = DATO. Contenido externo (web/tools) marcado **no confiable**.
- **Tools**: allowlist + permisos mínimos por agente; acciones de riesgo (enviar) **piden confirmación**; loop acotado.
- **Empresa**: topes (`max_subtareas`/`hops`/`model_calls`) anti fan-out; allowlist inter-agente; el gasto pasa por Finanzas.
- **Bóveda de secretos**: claves solo en `.env` (en `.gitignore`/`.dockerignore`), nunca en código, logs ni imagen.
- **Memoria y biométricos**: **100% local** (`data/`); cara/voz **nunca** a la nube; `--borrar` para olvidar.
- **Despliegue**: solo LAN, contenedor no-root/hardened. Remoto fuera de casa = Tailscale (opcional futuro).

---

## 8. Mejora continua (auditoría)

Cuando quieras (fin del día/semana), abrí **Claude Code + Opus** y corré un prompt de
[auditoria/](auditoria/): lee los `logs/*.jsonl`, detecta patrones y **propone**
mejoras o nuevos equipos. Vos aprobás e implementás **editando `config/teams.yaml`**
(agregar un equipo = editar config, sin código). Costo de API extra: **$0**.

---

## 9. Opcional futuro (no construido; NOVA ya es 100% funcional en local + LAN)

- Multi-dispositivo / **PWA**, acceso remoto **Tailscale** + mkcert.
- **Wake word** real ("Hey NOVA").
- Proveedores con **OAuth** real (Google Calendar, SMTP) detrás de las mismas interfaces de tools.
- Re-ingesta avanzada de ediciones del vault Obsidian; `sqlite-vec`/Qdrant a escala.
