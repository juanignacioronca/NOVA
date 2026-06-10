# Prompt 6 — Herramientas (tools layer)

> Pega todo lo que está **bajo la línea** en Claude Code, en el repo de NOVA (Prompts 1–5 andando, Python 3.12, en el Mac — no se necesita Docker aún). Mantén async, Registry, bóveda de secretos.

---

Lee `CLAUDE.md`. Esta fase le da **manos** a NOVA: una capa de herramientas que los agentes usan para *hacer* cosas (leer calendario, clima, buscar) y para *actuar* (agendar, recordar, enviar). La **seguridad es el centro de esta fase**: aquí es donde más aplican las buenas prácticas tipo OpenClaw (allowlist, permisos mínimos, confirmación de acciones, contenido externo no confiable).

## Objetivo
- Los agentes pueden invocar herramientas registradas con un protocolo **agnóstico de modelo** (no depende de function-calling del proveedor).
- "¿Qué tiempo hace?" → usa `clima`; "agéndame algo" → `agendar_evento` (te pide confirmar); una acción de riesgo (enviar correo) **no se ejecuta sin tu OK explícito**.
- Toda herramienta solo corre si está en la **allowlist** y el agente tiene **permiso**; el contenido externo (web, correo) entra marcado como **no confiable**.

## Construye

1. **Registro de herramientas** (extiende el Registry): cada tool declara `name`, `descripcion`, `args_schema` (validable), `riesgo` (`safe` lectura · `low` escritura reversible · `high` efecto sensible) y de qué `grupo`/`agentes` es invocable. `config/tools.yaml` = **allowlist** + permisos por agente (least-privilege). Solo lo listado es usable.

2. **Protocolo de invocación agnóstico de modelo:**
   - Una tool se expone al agente como `{name, descripcion, args_schema}`.
   - El agente que necesita una tool emite JSON `{"tool": "...", "args": {...}}` (parseo tolerante, como `Intent`). El `ToolExecutor` valida args contra el schema, chequea allowlist + permiso + riesgo, ejecuta y devuelve el resultado.
   - `BaseAgent.use_tool(name, args)` → resultado, o levanta `PermisoDenegado` / `RequiereConfirmacion`.
   - **Loop de tool-use acotado:** el agente puede encadenar pensar→tool→pensar→… con **máximo N pasos** (config, ej. 4) para evitar loops descontrolados (también es una medida de seguridad).
   - **Modo stub:** las tools devuelven resultados deterministas falsos para correr offline/sin claves.

3. **Niveles de riesgo + confirmación:**
   - `safe` (lectura) y `low` (ej. timer, recordatorio) → se ejecutan directo.
   - `high` (enviar correo/mensaje, borrar, gastar) → **requieren confirmación explícita del usuario**. Reusa el mecanismo de diálogo del Prompt 3: NOVA devuelve "Voy a enviar X a Y. ¿Confirmas?", guarda la acción pendiente en `WorldState`, y solo ejecuta con el "sí".

4. **Contenido externo no confiable:** todo resultado de tool que traiga contenido de afuera (web, correo, archivos) se envuelve con `marcar_no_confiable(contenido, fuente)` antes de pasarlo a un agente/modelo, para que **no se obedezcan instrucciones embebidas** (defensa anti-inyección del Prompt 3, ahora crítica).

5. **Set inicial de herramientas** (todas $0, sin claves para las de lectura):
   - `clima` — Open-Meteo (sin clave). `safe`.
   - `buscar_web` — DuckDuckGo (lib sin clave; pluggable a Brave/Tavily con clave después). Resultado → `marcar_no_confiable`. `safe`.
   - `buscar_lugar` — Nominatim/OpenStreetMap (sin clave, con `User-Agent` propio). `safe`. (Sirve al ejemplo del cerro.)
   - `leer_calendario` + `agendar_evento` — sobre un **calendario local** (store JSON/ICS que NOVA maneja). Lectura `safe`; agendar `low`. (Google Calendar/CalDAV detrás de la misma interfaz = futuro.)
   - `crear_recordatorio` / `set_timer` — `low`, alimentan los triggers proactivos del Prompt 4.
   - `enviar_correo` — `high`, **con confirmación**; backend pluggable/stub (SMTP/OAuth real = futuro). Demuestra el patrón de acción gated.

6. **Integración con el flujo:** el Conductor/agentes eligen tool según la tarea. Simple: respuestas rápidas usan `clima`/`calendario`/`timer`. Complejo: Estrategia usa `buscar_web`/`buscar_lugar`/`clima`; PMO usa `agendar_evento` (con confirmación). Cada invocación se **loggea** en el registro (tool, args, agente, permitido/denegado, confirmado, resultado breve) → insumo de la auditoría.

7. **Tests** (offline, mock HTTP, 3.12):
   - Allowlist y permisos por agente (denegado si no tiene permiso).
   - Tool `high` dispara confirmación y solo ejecuta con el "sí".
   - Resultado externo queda envuelto como no confiable.
   - El loop de tool-use respeta el tope N.
   - Tools en stub devuelven resultados deterministas; `pytest` pasa sin red ni claves.

## Reglas
- Python 3.12, async, type hints, docstrings breves.
- **Seguridad primero:** allowlist + permisos mínimos por agente + confirmación de acciones + contenido externo no confiable + loop acotado + logging de cada tool.
- Claves de tools (cuando las haya) solo desde `.env`. Respeta Registry/interfaces/bóveda de secretos.

## No hagas todavía
- Proveedores reales con OAuth (Google Calendar, correo SMTP real) → futuro, detrás de la misma interfaz.
- Equipos de nube completos → **Prompt 7**. Frontend/visual → fases siguientes.

## Criterio de aceptación
- Un agente invoca una tool por el protocolo JSON; una tool fuera de allowlist o sin permiso se rechaza; una tool `high` pide confirmación y solo corre con el "sí".
- El contenido web/externo entra marcado como no confiable.
- El set inicial de tools existe y funciona (real con red, stub sin red).
- `pytest` pasa offline.
- Actualiza `CLAUDE.md` §10 (Prompt 6 completo) y §11 (modelo de permisos de tools). Nota qué sigue → **Prompt 7 (Grupo Nube: equipos reales + sub-agentes + skills inter-agente)**.
