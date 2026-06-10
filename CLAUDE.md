# NOVA — CLAUDE.md

> Documento maestro del proyecto. **Claude Code lo lee al inicio de cada sesión** y es la fuente de verdad. Cada sesión de trabajo = **un prompt acotado** del `prompts/ROADMAP.md`. No intentes construir todo de una; confía en este archivo y no repitas contexto (token-efficient).

---

## 1. Qué es NOVA

NOVA es un asistente personal multiagente, tipo Jarvis, **siempre activo** y **multimodal** (audio, texto, video). Entiende qué quiere lograr el usuario y resuelve: **lo simple en local** (rápido y gratis), **lo complejo en la nube** (modelos grandes). Un único **Conductor** es la cara que habla con el usuario, le pregunta a los equipos de agentes y entrega la respuesta. Objetivo de diseño: **máxima capacidad con gasto $0**.

---

## 2. Principios (no negociables)

- **De cero, arquitectura propia.** NO usar frameworks de agentes (LangGraph, CrewAI, AutoGen). Construir **liviano y a medida**.
- **Patrón Registry** como unidad central: agentes y herramientas se registran y se descubren por nombre/grupo/skill.
- **Local-first** para lo que corre siempre o seguido (Ollama, $0). **Nube free-tier** solo para lo complejo y poco frecuente.
- **Presupuesto $0:** Gemini Flash, Groq y OpenRouter (free tiers) + Ollama local. Opus 4.8 es **opcional**.
- **Bóveda de secretos:** las claves van en `.env`, **NUNCA** en el código ni en el repo. El free-tier de Gemini puede entrenar con los prompts → **nunca** mandar claves/credenciales/datos sensibles a la nube.
- **Async** (`asyncio`) en todo el núcleo: loop de percepción, bus de mensajes y agentes.
- **Incremental:** un prompt = una fase coherente. El estado se marca en §10.

---

## 3. Arquitectura

```
        [ AUDIO  TEXTO  VIDEO ]        ← Percepción (loop continuo, local)
                  │                       video en modo Sentinela (muestreo adaptativo)
                  ▼
          [ ESTADO DEL MUNDO ]         ← memoria de trabajo · caché vivo de la memoria
                  ▼
   [ CONDUCTOR: comprensión+orquestación+respuesta ]   ← ÚNICA cara que habla con el usuario
                  │   entiende intención + clasifica complejidad
        ┌─────────┴──────────┐
        ▼                    ▼
 [ GRUPO LOCAL ]       [ GRUPO NUBE ]          ambos usan → [ HERRAMIENTAS ] y [ MEMORIA ]
 rápido, siempre       PMO · Transversales
 activo, Ollama        (Estrategia, Finanzas)
                       · Áreas (con sub-agentes)
        └─────────┬──────────┘
                  ▼
            [ SALIDAS ]          voz + pantalla (HTML dinámico) · botones de modalidad

 [ AUDITORÍA ]  asíncrona, FUERA del flujo → corre en Claude Code + Opus 4.8 (ver §9)
```

- **Percepción (local):** audio→STT, texto, video→fotogramas con **modo Sentinela** (si la imagen no cambia, baja la frecuencia de muestreo). Alimenta el Estado del Mundo.
- **Estado del Mundo:** store compartido (qué pasa / qué pediste / qué viene); caché vivo de la Memoria.
- **Conductor (comprensión + orquestación + respuesta):** la única cara que habla con el usuario. Entiende la intención y **clasifica complejidad**: simple → Grupo Local; complejo → Grupo Nube. Le pregunta a los agentes, integra y responde. Si falta info, **pregunta** antes de asumir.
- **Grupo Local (Ollama):** Sentinela/visión, Oído (STT), Voz (TTS), Memoria/contexto, Respuestas rápidas.
- **Grupo Nube (free-tier):** PMO/Orquestación; Transversales (Estrategia, Finanzas); Áreas (Inversiones, Ecommerce/Luthenox, Laboral, Fitness, Idiomas, Recreacional, Desarrollo personal, Multifacético). Cada equipo tiene **sub-agentes** (ver `config/models.yaml`).
- **Herramientas (tools):** entrada (calendario, mail, web, mapas, clima, cámara/mic) y salida (agendar, enviar, TTS, pantalla, dispositivos). Las usan local y nube; se registran en el Registry.
- **Memoria (fase posterior):** grafo + vectores + capa **Obsidian** (markdown navegable). Guarda los **registros** de todos los agentes.
- **Auditoría (asíncrona, fuera del flujo):** NO corre dentro de NOVA. El usuario la ejecuta en **Claude Code + Opus 4.8** con prompts fijos en `audit/prompts/`, que leen `logs/` y proponen mejoras o nuevos equipos. Nada se crea sin aprobación del usuario.
- **Salidas:** voz + pantalla (HTML dinámico que muestra **proceso y resultados**). Botones de modalidad (solo voz / solo pantalla / ambos), los activa el usuario.

---

## 4. La regla de modelos

| Rol | Modelo |
|---|---|
| Líderes, planificadores, redactores, tutores, especialistas | **Gemini Flash** (gratis, multimodal) |
| Investigadores / deep research | **Groq Llama 3.3 70B** (gratis, rápido) |
| Razonamiento pesado / análisis cuantitativo | **DeepSeek R1** (gratis, OpenRouter) |
| Estructurado, cálculos simples, corrección, seguimiento | **Local** (Qwen 2.5 7B / Llama 3.2 3B) |
| Conductor | **Local 7B** (simple) + **Gemini Flash** (complejo/multimodal) · Opus opcional |
| Auditoría | **Claude Code + Opus 4.8** (asíncrona) |

**Regla de costo:** lo que corre mucho/siempre → local; lo complejo/poco frecuente → nube free repartido entre proveedores (para no agotar cuotas); Opus solo donde rinde (Conductor en momentos críticos, Auditoría). El mapa completo agente→modelo vive en `config/models.yaml` (fuente de verdad).

---

## 5. Capa de modelos, proveedores y `.env`

- Un único punto de entrada: `model_router.complete(agent, messages, **opts)` elige proveedor + modelo desde `config/models.yaml`.
- Sintaxis del mapa: `proveedor:modelo` (ej. `gemini:gemini-2.5-flash`, `groq:llama-3.3-70b-versatile`, `openrouter:deepseek/deepseek-r1:free`, `ollama:qwen2.5:7b`).
- Proveedores OpenAI-compatibles (un mismo cliente): **Groq, OpenRouter, DeepSeek, y Ollama local**. **Gemini** usa su cliente (o su endpoint compatible).
- **Rate limits (429):** retry con backoff exponencial (1s, 2s, 4s, 8s) y **fallback** a otro proveedor o a local.
- **Modo STUB:** si no hay proveedor/clave disponible, el router devuelve respuestas deterministas de prueba, para poder testear el cableado **sin modelos ni claves**.
- `.env` (ejemplo en `.env.example`): `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY` (opcional), `OLLAMA_HOST`. **`.env` nunca se commitea** (va en `.gitignore`).

---

## 6. Estructura del repo

```
nova/
  CLAUDE.md
  .env.example
  .gitignore
  pyproject.toml
  src/nova/
    core/
      conductor.py      # comprensión + orquestación + respuesta
      world_state.py    # estado del mundo (memoria de trabajo)
      message_bus.py    # bus de mensajes entre agentes (async)
      registry.py       # Registry: registra/descubre agentes y skills
      agent.py          # BaseAgent (clase base)
    models/
      model_router.py   # capa de modelos (elige proveedor/modelo)
      providers/        # ollama, openai_compatible (groq/openrouter/deepseek), gemini
    config/
      models.yaml       # mapa agente → modelo (roster)
    logging/
      registro.py       # registros JSONL de cada acción de agente
    perception/         # (fase posterior)
    memory/             # (fase posterior)
    tools/              # (fase posterior)
    agents/             # (fase posterior) equipos local + nube/*
    cli.py              # harness de prueba por texto
    app.py              # (fase posterior) FastAPI + WebSocket
  prompts/              # ROADMAP.md + prompts por fase
  audit/prompts/        # prompts fijos de auditoría (para Claude Code)
  logs/                 # registros (los lee la auditoría)
  tests/
```

---

## 7. Stack

- **Backend:** Python **3.11+** (desde Prompt 4; dev en venv `.venv` con Python 3.12 de Homebrew). `asyncio`, FastAPI + WebSocket (fase posterior). `httpx` para HTTP.
- **Modelos:** Ollama (local); Gemini/Groq/OpenRouter/DeepSeek vía OpenAI-compatible.
- **Percepción (Prompt 4):** `sounddevice` (mic), `silero-vad` (VAD), `faster-whisper` (STT), `opencv` (cámara), `piper-tts` (voz). Extra opcional `[perception]`; se importan **perezosamente** (sin ellas, esa fuente degrada y los tests corren igual). En macOS: `brew install portaudio ffmpeg`.
- **Config:** YAML (`models.yaml`, `perception.yaml`). **Logs:** JSONL.
- **Frontend (fase posterior):** PWA (Vite + TypeScript + Three.js) — reusar el concepto de la visualización supernova de v1; consumirá el stream de `TraceEvent`.
- **Dev:** Mac Apple Silicon (Ollama + Metal). **Prod:** ASUS con GPU dedicada (Docker → Prompt 5).

---

## 8. Convenciones

- **Registry:** todo agente y herramienta se registra con `name`, `group` (`local` | `nube`) y `skills`.
- **BaseAgent:** interfaz común — `name`, `group`, `model`, `async handle(task) -> result`, y enviar/recibir por el bus.
- **MessageBus:** mensajería async entre agentes (para trabajos mixtos / skills inter-agente).
- **WorldState:** store compartido async-safe.
- **Registro:** cada acción de agente → **una línea JSONL** en `logs/` con `{ts, agente, grupo, tarea, decisión, modelo, resultado_breve}`. Esto es lo que lee la auditoría.
- Identificadores en **inglés**; comentarios y docs en **español** está OK.
- **Tests con pytest** en cada fase.

---

## 9. Auditoría (cómo funciona)

No es un servicio dentro de NOVA. Es **asíncrona**: cuando el usuario quiere (ej. fin del día/semana), abre **Claude Code con Opus 4.8** y corre uno de los **prompts fijos** de `audit/prompts/`. Ese prompt lee todos los `logs/`, detecta patrones (ej. "5 consultas legales resueltas por el Multifacético") y **propone** mejoras o nuevos equipos. El usuario aprueba en "modo mejora". Costo extra de API: **$0** (usa su Pro).

---

## 10. Estado actual

- **Fase:** Prompt 6 — Herramientas (tools layer) ✅ **COMPLETO**. NOVA tiene **manos**: los agentes invocan herramientas con un protocolo JSON agnóstico de modelo, con la **seguridad en el centro** (allowlist + permisos por agente + confirmación de acciones + contenido externo no confiable + loop acotado + logging).

### Construido (Prompt 6)
- [x] **Registro de tools + allowlist** (`config/tools.yaml`): cada tool declara `name`, `descripcion`, `args_schema`, `riesgo` (`safe`/`low`/`high`) y `grupos`. Solo lo listado en `allowlist` es usable; `permisos` por agente = **least-privilege** (lo no listado, denegado). Tools registradas en el Registry.
- [x] **Protocolo agnóstico de modelo** (`tools/executor.py`): el agente emite `{"tool": "...", "args": {...}}` (parseo tolerante, `parse_tool_call`); el `ToolExecutor` valida args contra el schema, chequea allowlist + permiso + riesgo, ejecuta, envuelve lo externo y **registra** (tool, args, agente, permitido/denegado, confirmado, resultado). `BaseAgent.use_tool(name, args)` levanta `PermisoDenegado`/`RequiereConfirmacion`. **Loop de tool-use acotado** (`tool_loop`, máx. N=`defaults.max_steps`).
- [x] **Riesgo + confirmación:** `safe`/`low` → directo; `high` → guarda `pending_action` en el WorldState y NOVA devuelve "¿Confirmás?"; **solo ejecuta con el "sí"** (reusa el diálogo del Prompt 3, integrado en el Conductor). `no` cancela.
- [x] **Contenido externo no confiable:** los resultados de tools `externo` (web, lugares) pasan por `marcar_no_confiable(contenido, fuente)` antes de llegar a un agente/modelo → no se obedecen instrucciones embebidas (defensa anti-inyección del Prompt 3, acá crítica).
- [x] **Set inicial (real con red, stub sin red):** `clima` (Open-Meteo, safe), `buscar_web` (DuckDuckGo, safe, externo), `buscar_lugar` (Nominatim/OSM, safe, externo), `leer_calendario` (safe) + `agendar_evento` (low) sobre store local JSON, `crear_recordatorio`/`set_timer` (low, alimentan los avisos proactivos del Prompt 4), `enviar_correo` (high, con confirmación; backend stub). Degradan a stub ante falta de red (`NOVA_FORCE_STUB=1` los fuerza, offline/tests).
- [x] **Integración:** `respuestas_rapidas` mapea intención→tool (clima/timer/recordatorio/calendario); `estrategia_investigador` usa `buscar_web` (resultado ya marcado no confiable). Cada invocación queda en el registro JSONL.
- [x] **Tests offline (39/39):** allowlist + permisos (denegado sin permiso/fuera de allowlist), `high` pide confirmación y solo corre con el "sí", contenido web marcado no confiable, loop respeta el tope N, tools en stub deterministas, integración por el Conductor. Sin red ni claves.

### Construido (Prompt 5)
- [x] **Servicio** (`app.py`, FastAPI + WS): `GET /health`, `POST /chat` (texto→respuesta+traza), `WS /ws` (streamea `TraceEvent` en vivo + respuesta, reusa el stream del Prompt 3), `GET /` (página mínima HTML/JS inline, sin deps, para hablarle desde el navegador del teléfono). Conductor **por request** (registry/bus aislados) sobre un WorldState compartido. Bind por entorno (`NOVA_HOST/PORT`); la restricción a LAN se hace en el compose. Extra `[server]` (fastapi, uvicorn).
- [x] **Empaquetado:** `Dockerfile` multi-stage (`python:3.12-slim`, venv → runtime liviano), usuario **no-root**, `HEALTHCHECK` contra `/health`, sin `.env`/claves en la imagen. `package-data` incluye los YAML en el wheel (instalación no editable). `NOVA_LOG_DIR` para logs escribibles. `.dockerignore` (excluye `.venv/.env/logs/tests/...`).
- [x] **Compose:** `docker-compose.yml` (nova + ollama; `OLLAMA_HOST=http://ollama:11434`; modelos en volumen persistente; `restart: unless-stopped`; **puerto de nova solo en la LAN** vía `${NOVA_LAN_IP}`, Ollama **sin** publicar; **hardening**: `read_only`, `tmpfs /tmp`, `cap_drop: ALL`, `no-new-privileges`, límites de CPU/mem; percepción off). `docker-compose.gpu.yml` (override NVIDIA para Ollama).
- [x] **Despliegue:** `deploy/README.md` (pasos ASUS Linux + nota Windows/WSL2 + GPU toolkit + **advertencia: no exponer a internet; remoto = Tailscale en Prompt 7**), `deploy/up.sh` (compose + pull de modelos), `deploy/smoke.sh` (build + run CPU-only + chequea `/health`,`/chat`,`/`).
- [x] **Tests offline (28/28):** `/health`, `/chat` (stub→local), `/` y `WS /ws` (traza + respuesta) responden; app levanta sin red ni claves. Validado además: el wheel no-editable incluye `config/*.yaml`, y el compose ata nova a la LAN con hardening (ollama interno).

### Construido (Prompt 4)
- [x] **Entorno 3.11+:** `pyproject` `requires-python=">=3.11"`; venv `.venv` (Python 3.12 de Homebrew). El código existente (3.8-compat) corre igual. Extra opcional `[perception]` con las libs pesadas (lazy import → sin ellas, la fuente degrada y los tests corren).
- [x] **Loop de percepción** (`perception/loop.py`): orquesta fuentes + scheduler como tasks asyncio; cada runnable `start()/run(stop)/stop()`; si degrada, se omite con aviso y el resto sigue; apagado limpio con Ctrl-C.
- [x] **Audio** (`perception/audio.py`): mic (`sounddevice`) → **VAD** (Silero, gating) → **STT** (faster-whisper) → el texto entra al Conductor **como si lo escribiera** (reusa comprensión + anti-inyección; lo percibido es DATO). Wake-word `openWakeWord` (`hey_jarvis`) como placeholder detrás de flag, off. Backends inyectables.
- [x] **Video + Sentinela** (`perception/vision.py`): cámara (`opencv`) con **muestreo adaptativo** (diff simple): sin cambios por `idle_seconds` → baja a `idle_interval`; ante cambio relevante → vuelve a `active_interval` y manda el frame al modelo `sentinela_vision` (entra al WorldState). Backends inyectables (cámara/diff/describe/clock/sleeper).
- [x] **Voz (TTS)** (`output/voz.py`): `VozTTS` con Piper (lazy) + `OutputManager` (pantalla siempre, voz si hay TTS). Barge-in → Prompt 7.
- [x] **Grupo Local (reales):** `SentinelaAgent` (visión, mantiene "qué/quién está en cámara"), `MemoriaContextoAgent` (memoria de trabajo + match simple "la lista del papá"), `RespuestasRapidasAgent`. Roster: agregado `sentinela_vision` (local-first + fallback nube).
- [x] **Avisos proactivos** (`core/proactivo.py`): scheduler que revisa triggers del WorldState (recordatorios con hora, eventos de visión "alguien se acerca"); `conductor_simple` redacta en tono NOVA; respeta la separación de seguridad (lo percibido se envuelve con `marcar_no_confiable`).
- [x] **Daemon + lanzador:** `python -m nova.run` (loop completo, traza en vivo, Ctrl-C limpio) y `nova.command` a doble clic. `nova.chat` (texto) sigue. Config en `config/perception.yaml`.
- [x] **Tests offline (24/24):** Sentinela baja/sube la frecuencia con cambios simulados, audio→WorldState (+ inyección percibida marcada), trigger proactivo dispara aviso (sin repetir), fuente degradada no tira el loop. Mockea hardware/modelos; sin red ni claves.

### Construido (Prompt 3)
- [x] **Motor de comprensión** (`core/comprension.py`): `comprender(texto, images, contexto) -> Intent` (`intencion, entidades, faltantes, complejidad, confianza, multimodal`). Pide **JSON estricto** al modelo, parsea con tolerancia (reintenta una vez "solo JSON"), escala a `conductor_complex` si baja confianza, y cae a **heurística** en stub. Detecta inyección.
- [x] **Multimodal (paso 1: imágenes):** `Conductor.attend(texto, images=None)` arma mensajes formato visión OpenAI-compatible (`image_url` data-URL base64) y enruta a `conductor_vision` (en `models.yaml`: `gemini` primario + fallback local `ollama:qwen2.5vl:7b`, **forma de lista = cadena de fallback por-agente** en el router). `--img` en CLI, `/img <ruta> <texto>` en el REPL.
- [x] **Diálogo de aclaración:** si faltan datos o la confianza < umbral → **una** pregunta concisa + `pending_clarification` en `WorldState`; el siguiente mensaje se **fusiona** y reevalúa (máx. 2 rondas; luego procede avisando el supuesto).
- [x] **Ruteo + síntesis:** simple → local; complejo → PMO por bus y `conductor_complex` **sintetiza** (no pegotea); en stub cae al plan determinista.
- [x] **Seguridad anti-inyección** (`core/security.py`): instrucciones de NOVA SOLO en `system`; texto del usuario/externo en `user` como DATO. `marcar_no_confiable(contenido, fuente)` para contenido externo (fases siguientes). `detectar_inyeccion` marca intentos de override en la traza **sin obedecerlos**. Documentado en **§11**.
- [x] **Traza estructurada** (`core/trace.py`): `TraceEvent(ts, etapa, agente, grupo, modelo, detalle, estado)`. El Conductor mantiene `last_trace` y los **emite** por `on_event` (callback/cola async) además del JSONL. El REPL imprime el flujo en vivo; el frontend (Prompt 7) consumirá el mismo stream. (Sin frontend todavía.)
- [x] **Tests offline (19/19):** comprensión estructurada, ambigüedad→pregunta→fusión, clasificación, inyección marcada y system intacto, imagen→modelo de visión. Sin red ni claves.

### Construido (Prompt 2)
- [x] **Cliente OpenAI-compatible único** (`models/providers/openai_compatible.py`, async, solo `httpx`) para TODOS los proveedores cambiando `base_url`+clave: `ollama` (`/v1`, clave dummy) · `groq` · `openrouter` (+ headers `HTTP-Referer`/`X-Title`) · `deepseek` · `gemini` (endpoint compatible). `gemini_client`/`ollama_client` quedaron como wrappers finos (+ `ollama_models()` para listar `/api/tags`).
- [x] **`model_router` real:** cadena de resiliencia **primario → 429/5xx/timeout (retry backoff 1,2,4,8s) → `fallback` (Ollama) → stub**. Si falta la clave, salta directo al fallback (sin reintentar) con aviso a stderr (nunca loggea la clave). `complete_meta` devuelve qué `proveedor:modelo` respondió de verdad → se registra en el campo `modelo` del JSONL (incluido fallback/stub).
- [x] **`nova/doctor.py`** (`python -m nova.doctor`): estado por proveedor (OK / sin clave / error + latencia) y modelos pulled de Ollama. No revienta si algo está caído.
- [x] **`nova/chat.py`** (`python -m nova.chat`): REPL por texto; muestra respuesta + traza compacta (intención · complejidad · agente(s) · `proveedor:modelo`). `salir`/`exit`/Ctrl-C salen limpio.
- [x] **Lanzadores a doble clic** (macOS, ejecutables): `run-nova.command` (chat) y `doctor.command`, con `cd "$(dirname "$0")"`, intérprete overrideable con `NOVA_PYTHON`, ventana que queda abierta. Nota Gatekeeper (1ª vez: clic derecho → Abrir).
- [x] **`.env.example`** con las 5 claves + de dónde sacarlas gratis (AI Studio, console.groq.com, openrouter.ai). `.env` sigue en `.gitignore`.
- [x] **Tests offline (11/11):** parseo `proveedor:modelo`, base_url/clave por proveedor, 429→fallback→stub, falta-clave→fallback. Sin red ni claves.
- [x] **Verificado:** con clave real (simulada con proveedor falso) una consulta compleja la responde el modelo real (`groq`/`gemini` visibles en traza y registro); sin claves cae a local/stub sin error.

### Construido (Prompt 1)
- [x] **Scaffold:** `pyproject.toml` (httpx, pyyaml, pytest, pytest-asyncio), `.gitignore` (`.env`, `logs/`), `.env.example`, `README.md`. Layout `src/nova/`.
- [x] **Capa de modelos:** `models/model_router.py` (`complete(agent, messages)`), proveedores `ollama` · `openai_compatible` (Groq/OpenRouter/DeepSeek) · `gemini`. 429 → backoff (1,2,4,8s) → `fallback` → **stub**. Claves desde `.env`.
- [x] **Roster:** `config/models.yaml` (agente→modelo, `defaults.fallback` + `stub_if_unavailable`).
- [x] **Núcleo async:** `core/registry.py` (`@register` + `Registry.add`), `core/agent.py` (`BaseAgent`: `handle`, `think`, helpers de bus), `core/message_bus.py` (`request`/`reply` + `publish`/`subscribe`), `core/world_state.py` (store async-safe), `core/task.py` (`Task`/`Result`), `core/conductor.py` (comprensión→ruteo→respuesta, log + evento por paso).
- [x] **Agentes stub:** `RespuestasRapidasAgent` (local), `PMOAgent` (nube, descompone + consulta a Estrategia **por el bus**), `EstrategiaInvestigadorAgent` (nube).
- [x] **Registro:** `logging/registro.py` → una línea JSONL por acción en `logs/AAAA-MM-DD.jsonl`.
- [x] **CLI:** `python -m nova.cli "<texto>"` imprime traza (intención, complejidad, agentes, respuesta) + ruta del registro.
- [x] **Tests:** `pytest` (5/5) — simple→local, complejo→PMO→Estrategia (por bus), se escribe registro, router cae a stub.

### Notas
- **Python:** desde Prompt 4 el dev corre en venv `.venv` (Python 3.12); el código se mantiene 3.8-compat (`from __future__ import annotations`), así que no hubo que tocar lo existente.
- Instalar: `pip install -e ".[dev]"` (núcleo/texto) y opcional `pip install -e ".[perception]"` (audio/video/voz). Correr sin claves = modo stub automático.

### Qué sigue (Prompt 7 — Grupo Nube: equipos reales + sub-agentes + skills inter-agente)
- **Equipos de nube reales** (PMO con sub-agentes, Transversales Estrategia/Finanzas, Áreas) que reemplazan los stubs, coordinándose por el `MessageBus` con **skills inter-agente** y usando la capa de herramientas del Prompt 6.
- Probablemente también: acceso remoto fuera de casa (Tailscale) y frontend/PWA con la vista de flujo en vivo (consume el stream de `TraceEvent`).
- Tampoco hay aún: wake-word real "Hey NOVA" y barge-in; memoria persistente (grafo/vectores/Obsidian); proveedores reales con OAuth (Google Calendar, SMTP real) detrás de las mismas interfaces de tools.
- _(Actualizar esta sección a medida que cada prompt del ROADMAP se completa.)_

---

## 11. Seguridad (buenas prácticas, tipo OpenClaw)

La defensa central contra **prompt injection** es **estructural**, no un filtro de texto:

- **Separación system / usuario.** Las instrucciones de comportamiento de NOVA van **solo** en el rol `system`. El texto del usuario y **todo contenido externo** (web, archivos, mails, mensajes) van en `user`. **Nunca** se concatena contenido no confiable dentro del system prompt.
- **Contenido externo = DATOS, no instrucciones.** Se envuelve con `core.security.marcar_no_confiable(contenido, fuente)`, que lo delimita y aclara que no debe obedecerse. Las herramientas/web de fases siguientes pasan todo por ahí antes de dárselo al modelo.
- **Alerta complementaria.** `core.security.detectar_inyeccion(texto)` detecta patrones de override ("ignora tus instrucciones", "actúa como…", "system:", etc.). NO se actúa sobre ellos: se marca `inyeccion_detectada` en el `Intent` y un evento `seguridad` (estado `alerta`) en la traza. La separación estructural es lo que protege; esto solo avisa.
- **Bóveda de secretos.** Las claves viven solo en `.env` (en `.gitignore`), nunca en el código ni en logs. El free-tier de Gemini puede entrenar con los prompts → **nunca** mandar claves/credenciales/datos sensibles a la nube.
- **Mínimo privilegio (a futuro).** Cuando se agreguen herramientas con efectos (enviar mail, agendar, controlar dispositivos), requerirán confirmación explícita y quedarán registradas.

### 11.1 Privacidad de la percepción (Prompt 4)

- **Lo percibido es input NO confiable.** El audio transcripto y los eventos de visión se tratan como DATO (no instrucción): entran al Conductor por el rol `user`, con la misma defensa anti-inyección del texto. La fuente de audio marca `inyeccion` en el evento si detecta un intento de override; los avisos proactivos envuelven lo percibido con `marcar_no_confiable`.
- **Local-first / los crudos no salen.** El audio y el video crudos, y la transcripción, se quedan **en local**. A la nube solo va texto (o un fotograma puntual) **cuando el Conductor escala algo complejo**, y **nunca** secretos ni credenciales (bóveda de secretos). La visión Sentinela usa modelo **local** por defecto (`sentinela_vision`: Ollama primario), con nube solo como fallback.
- **Permisos del SO (TCC).** macOS pide permiso de micrófono y cámara en la 1ª ejecución; sin permiso (o sin hardware/modelo), esa fuente **degrada con aviso** y el resto sigue.

### 11.2 Despliegue seguro (Prompt 5)

- **Solo LAN, nunca WAN.** El puerto de `nova` se publica atado a `NOVA_LAN_IP` (default `127.0.0.1`), nunca a `0.0.0.0` público. **No abrir puertos del router a internet.** El acceso remoto fuera de casa se hace con **Tailscale** (Prompt 7), que no expone nada al WAN.
- **Superficie mínima.** Ollama **no** publica puertos (solo red interna del compose); solo `nova` es alcanzable, y solo en la LAN.
- **Contenedor endurecido.** No-root (`uid 10001`), `read_only` rootfs + `tmpfs /tmp`, `cap_drop: ALL`, `no-new-privileges`, sin host network, límites de CPU/memoria, `restart: unless-stopped`.
- **Secretos fuera de la imagen.** Las claves llegan **solo en runtime** por `.env`/`env_file`; jamás se copian a la imagen (`.dockerignore` excluye `.env`) ni se loggean. La imagen no contiene `.env`.
- **Percepción off en el servidor.** Un contenedor headless no tiene mic/cámara; capturar dispositivos dentro del contenedor es opción avanzada documentada. La solución limpia (captura en el dispositivo, cómputo en el ASUS) es del Prompt 7.

### 11.3 Modelo de permisos de herramientas (Prompt 6)

La capa de tools es donde más se concretan las buenas prácticas. Reglas:

- **Allowlist explícita.** Solo las herramientas en `config/tools.yaml → allowlist` existen para el sistema. Nada se ejecuta "porque sí".
- **Least-privilege por agente.** `permisos` lista, por agente, qué tools puede invocar; lo no listado se **deniega** (`PermisoDenegado`). Ej.: `estrategia` puede buscar en la web pero **no** enviar correos; `memoria`/`sentinela` no usan tools.
- **Riesgo y confirmación.** `safe` (lectura) y `low` (escritura reversible) corren directo; `high` (enviar, borrar, gastar) **exige confirmación explícita** del usuario; la acción queda en `pending_action` y solo se ejecuta con el "sí".
- **Contenido externo = DATOS.** Todo resultado de tool `externo` (web, lugares, y a futuro correo/archivos) se envuelve con `marcar_no_confiable` antes de llegar a un modelo → no se obedecen instrucciones embebidas.
- **Validación + loop acotado.** Los args se validan contra `args_schema`; el loop pensar→tool→pensar tiene tope `max_steps` (evita loops descontrolados; es también una medida de seguridad).
- **Auditoría.** Cada invocación (permitida o denegada, con args y resultado breve) se escribe en el registro JSONL → insumo de la auditoría.
- **Claves de tools** (cuando las haya, ej. Brave/Tavily/SMTP) solo desde `.env`, nunca en código ni en logs.
