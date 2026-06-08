# Prompt 2 — Capa de modelos real

> Pega todo lo que está **bajo la línea** en Claude Code, en el repo de NOVA (con `CLAUDE.md` y el esqueleto del Prompt 1 ya andando). **Mantén compatibilidad con Python 3.8** (el Mac está en 3.8.6): usa solo `httpx`, nada de SDKs que exijan 3.9+.

---

Lee `CLAUDE.md`. Esta fase hace que la capa de modelos llame **de verdad** a los proveedores (Ollama local + Gemini/Groq/OpenRouter), con verificación, manejo de errores y lanzadores para probar a doble clic. El modo stub queda solo como último recurso.

## Objetivo
- `python -m nova.doctor` revisa cada proveedor y dice cuáles están OK / sin clave / con error (+ latencia), y lista los modelos de Ollama disponibles.
- `python -m nova.chat` abre un **chat interactivo por texto** con NOVA: escribo, responde, y veo qué proveedor/modelo contestó. `salir` termina.
- Dos lanzadores **a doble clic** (macOS) para no usar la terminal: uno abre el chat, otro corre el doctor.
- Con una clave de Gemini o Groq puesta, una consulta compleja la responde el modelo **real** (visible en la traza y el registro). Sin claves, sigue cayendo a local/stub sin reventar.

## Construye

1. **Cliente OpenAI-compatible único** (`models/providers/openai_compatible.py`, async, `httpx`) que sirva a TODOS los proveedores cambiando `base_url` + `api_key`:

   | proveedor | base_url | clave (.env) |
   |---|---|---|
   | `ollama` | `${OLLAMA_HOST:-http://localhost:11434}/v1` | (dummy, no requiere) |
   | `groq` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` |
   | `openrouter` | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` |
   | `deepseek` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` (opcional) |
   | `gemini` | `https://generativelanguage.googleapis.com/v1beta/openai/` | `GEMINI_API_KEY` |

   - Formato chat completions estándar. Para OpenRouter agrega headers `HTTP-Referer` y `X-Title` (valor libre, ej. `"NOVA"`). Timeout ~60s.
   - El `gemini_client.py` del Prompt 1: pásalo a un wrapper fino que delega en este cliente con la base de Gemini (o elimínalo y enruta `gemini:` por aquí).

2. **`model_router.complete(agent, messages, **opts)`** actualizado:
   - Resuelve `proveedor:modelo` desde `config/models.yaml` y arma el cliente correcto.
   - **Sin stub si hay un proveedor real disponible.** Stub solo como último eslabón.
   - **Cadena de resiliencia:** primario → en 429/5xx/timeout, retry con backoff (1,2,4,8s) → si falla, `defaults.fallback` (Ollama local) → si tampoco, stub.
   - **Registra el modelo que realmente respondió** (incluyendo si fue fallback) en el campo `modelo` del registro JSONL.
   - Si falta la clave de un proveedor, salta directo al fallback (sin reintentar en vano) y deja un aviso claro.

3. **`nova/doctor.py`** (`python -m nova.doctor`):
   - Por cada proveedor con clave: hace un `complete` mínimo ("responde OK") y reporta estado + latencia.
   - Lista modelos de Ollama (GET `${OLLAMA_HOST}/api/tags`).
   - Verde/rojo según qué falta. No revienta si un proveedor está caído.

4. **`nova/chat.py`** (`python -m nova.chat`):
   - REPL: lee `tú> `, llama `Conductor.attend`, imprime la respuesta de NOVA + una línea de traza compacta (intención · complejidad · agente(s) · `proveedor:modelo` que respondió). `salir`/`exit` o Ctrl-C terminan limpio.

5. **Lanzadores a doble clic** (macOS), en la raíz del repo, ejecutables (`chmod +x`):
   - `run-nova.command`: hace `cd` a la raíz del repo (detectada con `$(dirname "$0")`, sin rutas absolutas), usa el intérprete del entorno donde hice `pip install -e` y corre `python -m nova.chat`. Deja la ventana abierta.
   - `doctor.command`: igual pero corre `python -m nova.doctor`.
   - Comentario en ambos: la primera vez en macOS, clic derecho → **Abrir** (Gatekeeper).

6. **`.env.example`** actualizado con las 5 claves y un comentario de dónde se sacan **gratis**: Google AI Studio (Gemini), console.groq.com (Groq), openrouter.ai (OpenRouter). Verifica que `.env` siga en `.gitignore`.

7. **Tests** (offline, mockeando `httpx`):
   - Parseo `proveedor:modelo` y armado de base_url/clave por proveedor.
   - 429 → backoff → fallback a local → stub (con cliente mock que falla).
   - Si falta la clave de un proveedor, se salta al fallback.
   - `pytest` debe pasar **sin red ni claves**.

## Reglas
- **Compatibilidad Python 3.8** (solo `httpx`, sin SDKs 3.9+).
- Async, type hints, docstrings breves. Respeta Registry e interfaces de `CLAUDE.md`.
- **Bóveda de secretos:** claves solo desde `.env`; nunca loggear una clave.

## No hagas todavía
- Multimodal (imágenes/audio/video) → Prompt 3/4. Por ahora solo texto.
- Percepción, herramientas reales, equipos reales, frontend, Docker.

## Criterio de aceptación
- `python -m nova.doctor` reporta estado por proveedor + modelos de Ollama.
- `python -m nova.chat` conversa por texto; con clave real, una consulta compleja la responde el modelo real (visible en traza/registro); sin claves, cae a local/stub sin error.
- Los dos `.command` abren y corren a doble clic.
- `pytest` pasa offline.
- Actualiza §10 de `CLAUDE.md` (modelos reales conectados) y deja nota de qué sigue (Prompt 3).
