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

- **Backend:** Python 3.11+, `asyncio`, FastAPI + WebSocket. `httpx` para llamadas HTTP.
- **Modelos:** Ollama (local); SDK de Gemini; resto vía OpenAI-compatible.
- **Config:** YAML. **Logs:** JSONL.
- **Frontend (fase posterior):** PWA (Vite + TypeScript + Three.js) — reusar el concepto de la visualización supernova de v1.
- **Dev:** Mac Apple Silicon (Ollama + Metal). **Prod:** ASUS con GPU dedicada.

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

- **Fase:** Prompt 1 — esqueleto del núcleo ✅ **COMPLETO**. Corre de punta a punta con texto, rutea por complejidad y deja registro. Modo stub funciona sin claves ni Ollama.

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
- **Python:** el target es 3.11+ (§7), pero el esqueleto se mantiene **compatible con 3.8** (`from __future__ import annotations`) para correr en la máquina de dev actual (3.8.6). Al subir a 3.11+ no hay que cambiar nada.
- Instalar con `pip install -e ".[dev]"`. Correr sin claves = modo stub automático.

### Qué sigue (Prompt 2)
- Todavía NO hay: percepción real (audio/video), herramientas reales (calendario/mail/web/clima), equipos completos con sub-agentes, memoria persistente (grafo/vectores/Obsidian), frontend (PWA), `app.py` (FastAPI + WebSocket).
- _(Actualizar esta sección a medida que cada prompt del ROADMAP se completa.)_
