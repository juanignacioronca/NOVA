# Prompt 1 — Esqueleto del núcleo

> **Cómo usarlo:** pega TODO lo que está bajo la línea en Claude Code, en un repo vacío (con el `CLAUDE.md` ya en la raíz). Es la primera fase; construye solo el esqueleto que corre de punta a punta con texto.

---

Lee `CLAUDE.md` antes de empezar. Vas a construir el **esqueleto del núcleo de NOVA v2.0** desde cero. Solo el núcleo: debe correr de punta a punta con una entrada de **texto**, enrutar por complejidad y dejar registro. **Nada de audio, video, frontend, herramientas reales ni equipos completos todavía** (usa stubs donde haga falta).

## Objetivo
Que yo pueda correr en la terminal:
```
python -m nova.cli "ponme un timer de 10 minutos"      # simple → núcleo local
python -m nova.cli "organízame un finde de trekking"    # complejo → nube (PMO)
```
y ver: la intención entendida, la decisión de complejidad, el flujo entre agentes, la respuesta final del Conductor, y que se escribió un registro en `logs/`. **Debe funcionar sin claves ni modelos** (modo stub).

## Construye

1. **Scaffold del proyecto** según la estructura de `CLAUDE.md` §6: `pyproject.toml` (deps: `httpx`, `pyyaml`, `pytest`, `pytest-asyncio`), `.gitignore` (incluye `.env`, `logs/`), `.env.example` (claves de §5), `README.md` breve.

2. **`models/model_router.py`** — la capa de modelos:
   - `async def complete(agent: str, messages: list[dict], **opts) -> str`.
   - Lee `config/models.yaml`, resuelve el `proveedor:modelo` del agente.
   - Proveedores en `models/providers/`: `ollama_client.py`, `openai_compatible.py` (sirve Groq, OpenRouter y DeepSeek con la misma interfaz, cambia base_url + key), `gemini_client.py`. Claves desde `.env`.
   - **Manejo de 429:** retry con backoff exponencial (1s,2s,4s,8s); si sigue fallando, fallback al proveedor `defaults.fallback`.
   - **Modo STUB:** si `defaults.stub_if_unavailable: true` y no hay clave/Ollama, devuelve una respuesta determinista tipo `"[stub:{agent}] {resumen del último mensaje}"`. Así el esqueleto corre sin nada instalado.

3. **`config/models.yaml`** — el mapa agente→modelo (roster). Incluye al menos:
   ```yaml
   defaults:
     fallback: ollama:qwen2.5:7b
     stub_if_unavailable: true
   agents:
     conductor_simple:   ollama:qwen2.5:7b
     conductor_complex:  gemini:gemini-2.5-flash
     respuestas_rapidas: ollama:qwen2.5:7b
     memoria_contexto:   ollama:llama3.2:3b
     pmo_planificador:   gemini:gemini-2.5-flash
     pmo_coordinador:    gemini:gemini-2.5-flash
     pmo_integrador:     gemini:gemini-2.5-flash
     estrategia_investigador: groq:llama-3.3-70b-versatile
     estrategia_analista:     openrouter:deepseek/deepseek-r1:free
     finanzas_roi:       gemini:gemini-2.5-flash
   ```
   (Los tags de Ollama deben coincidir con los modelos que yo tenga pulled; deja un comentario avisando eso.)

4. **`core/registry.py`** — patrón Registry: registrar y descubrir agentes y herramientas por `name`, `group` y `skills`. Decorador `@register` o método `registry.add(agent)`.

5. **`core/agent.py`** — `BaseAgent`:
   - Atributos: `name`, `group` (`"local"|"nube"`), `model_key` (clave en models.yaml), `skills: list[str]`.
   - `async def handle(self, task: Task) -> Result` (override en cada agente).
   - Helper `async def think(self, messages)` que llama a `model_router.complete(self.model_key, messages)`.
   - Helpers para enviar/recibir por el `MessageBus`.

6. **`core/message_bus.py`** — `MessageBus` async: `publish(msg)`, `subscribe(agent_name)`, y request/response directo entre agentes (`async def request(to, payload) -> reply`). En memoria.

7. **`core/world_state.py`** — `WorldState`: store compartido async-safe (asyncio.Lock). Guarda hechos del contexto y una lista de eventos recientes. `get/set/append_event`.

8. **`core/conductor.py`** — `Conductor` (comprensión + orquestación + respuesta):
   - `async def attend(self, user_text: str) -> str`.
   - Paso 1 — **comprensión:** con `conductor_simple`, extrae intención + entidades y **clasifica complejidad** (`"simple" | "complejo"`). (En stub, usa heurística por palabras clave: timer/clima/calendario/recordar → simple; organiza/planifica/research/compara → complejo.)
   - Paso 2 — **ruteo:**
     - simple → delega al agente local `RespuestasRapidasAgent`, obtiene la respuesta.
     - complejo → crea un `Task`, lo manda vía bus al `PMOAgent`, que descompone y consulta a `EstrategiaAgent` (stub) y devuelve un resultado; el Conductor **integra** y arma la respuesta final.
   - Paso 3 — **respuesta:** devuelve el texto final (este sería el que va a voz/pantalla más adelante).
   - En **cada paso**, escribe un registro vía `registro.log(...)` y agrega un evento al `WorldState`.

9. **Agentes stub** en `agents/`:
   - `RespuestasRapidasAgent` (local): responde corto usando su modelo (o stub).
   - `PMOAgent` (nube): descompone el objetivo en 2-3 subtareas, pide ayuda a Estrategia por el bus, junta y devuelve un plan breve.
   - `EstrategiaInvestigadorAgent` (nube): devuelve un “hallazgo” stub.
   La lógica real vendrá en fases siguientes; aquí basta con que el flujo y los mensajes funcionen.

10. **`logging/registro.py`** — `log(agente, grupo, tarea, decision, modelo, resultado_breve)` escribe **una línea JSONL** por acción en `logs/AAAA-MM-DD.jsonl` con timestamp. Este es el insumo de la auditoría.

11. **`cli.py`** — `python -m nova.cli "<texto>"`: instancia el Conductor, corre `attend`, imprime de forma legible la traza (intención, complejidad, agentes que intervinieron, respuesta final) y confirma la ruta del registro escrito.

12. **`tests/`** (pytest + pytest-asyncio):
   - Una entrada simple se clasifica `simple` y la resuelve el núcleo local.
   - Una entrada compleja se clasifica `complejo`, pasa por `PMOAgent` y este consulta a Estrategia por el bus.
   - Se escribe al menos una línea de registro por corrida.

## Reglas
- **Async** en el núcleo. Tipado con type hints. Docstrings breves.
- Respeta el patrón Registry y las interfaces de `CLAUDE.md` §8.
- **Bóveda de secretos:** claves solo desde `.env`; nada hardcodeado; `.env` en `.gitignore`.
- Debe **correr sin claves ni Ollama** (modo stub) y también funcionar si después agrego claves/modelos.
- No agregues frameworks de agentes. Mantenlo liviano.

## Criterio de aceptación
- Los dos comandos del “Objetivo” corren y muestran rutas distintas (local vs nube) con respuesta final.
- `pytest` pasa.
- Se generan registros en `logs/`.
- Al terminar, **actualiza la sección §10 de `CLAUDE.md`** marcando lo construido y deja un comentario de qué sigue (Prompt 2).
