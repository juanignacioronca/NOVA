# Prompt 7 — Grupo Nube (equipos reales + sub-agentes + skills inter-agente)

> Pega todo lo que está **bajo la línea** en Claude Code, en el repo de NOVA (Prompts 1–6 andando, Python 3.12, en el Mac). Probable en stub/offline. Mantén async, Registry, bóveda de secretos, y la capa de tools del Prompt 6.

---

Lee `CLAUDE.md`. Esta fase reemplaza los equipos stub por la **"empresa" real**: PMO que descompone y reparte, transversales (Finanzas, Estrategia) que cruzan todo, áreas con sus sub-agentes, y **skills inter-agente** (agentes que se consultan entre sí). Clave: los equipos son **declarativos** (config, no 30 archivos), y todo va **acotado** en pasos/costo (lección de "autonomía descontrolada").

## Objetivo
- Una tarea compleja la maneja la empresa de verdad: el PMO la **descompone**, la **reparte** a las áreas correctas, los sub-agentes usan sus **tools** y se **consultan** entre sí, y el resultado se **integra** y vuelve al Conductor para la respuesta final.
- El ejemplo del cerro funciona end-to-end (en stub): Recreacional arma plan → Finanzas evalúa presupuesto → ajustan negociando → se integra.
- Agregar un equipo nuevo es **editar config**, no escribir código (esto habilita que la auditoría proponga equipos y tú los apruebes).

## Construye

1. **Roster declarativo** (`config/teams.yaml`): cada equipo con sus sub-agentes. Cada sub-agente = `{name, rol (system prompt corto), model_key (de models.yaml), tools (lista), puede_consultar (allowlist inter-agente)}`. Pobla con el roster ya definido (models.yaml / el diagrama): **PMO** (planificador, coordinador, integrador), **Estrategia** (líder, investigador, analista), **Finanzas** (líder, presupuesto, roi, controller), y **áreas** Inversiones, Ecommerce, Laboral, Fitness, Idiomas, Recreacional, Desarrollo personal, **Multifacético**. (Si falta algún `model_key` en models.yaml, agrégalo siguiendo la regla: líderes/redactores/tutores → gemini; investigadores → groq; razonamiento pesado → deepseek; estructurado → local.)

2. **Agente genérico por rol** (`agents/sub_agent.py`): un `SubAgent` manejado por el spec del roster — arma su system prompt desde `rol`, llama su modelo vía `model_router`, usa sus `tools` permitidas con el `tool_loop` del Prompt 6, y puede consultar a los agentes de su allowlist. **No** hand-codees 30 agentes; este genérico + el config los cubre.

3. **Orquestación PMO** (`core/empresa.py` o `agents/pmo/`):
   - **Planificador:** descompone el objetivo en subtareas; cada subtarea etiquetada con `area` destino, dependencias, y flags `requiere_finanzas` / `requiere_estrategia`.
   - **Coordinador:** despacha subtareas por el bus (en paralelo las independientes, secuencial las dependientes); enruta las flageadas por los **transversales**; junta resultados. Aplica los **topes** (ver punto 6).
   - **Integrador:** sintetiza los resultados de las subtareas en un entregable coherente.
   - El **Conductor** llama al PMO para lo complejo (reemplaza el PMO stub), recibe el entregable e hila la respuesta final (su síntesis del Prompt 3).

4. **Transversales (Finanzas, Estrategia) cruzando áreas:** las subtareas con `requiere_finanzas` pasan por Finanzas (evalúa presupuesto/ROI) y con `requiere_estrategia` por Estrategia (research/alineación), antes de integrar. Así el gasto siempre pasa por Finanzas (como en el diseño).

5. **Skills inter-agente:** `SubAgent.consultar(agente, payload)` por el bus, **solo** a quien esté en su `puede_consultar` (least-privilege), y **acotado** por `max_inter_agent_hops`. Demuestra la negociación Recreacional ↔ Finanzas (ajustar el plan para entrar en presupuesto).

6. **Topes de seguridad/costo** (config, ej. `empresa.yaml`): `max_subtareas` (ej. 8), `max_inter_agent_hops` (ej. 3), `max_model_calls` por petición (ej. 20). Si se alcanza un tope, se corta con aviso y se integra lo que haya. (Esto controla costo y evita fan-out descontrolado — importante con free-tiers y por seguridad.)

7. **Ruteo a áreas + fallback Multifacético:** el planificador mapea subtareas a áreas por tema; si ninguna calza → **Multifacético**, y se **loggea** como "tema sin equipo" (insumo para que la auditoría proponga crear el equipo). Respeta permisos de tools y contenido externo no confiable.

## Seguridad / costo
- Allowlist inter-agente + topes de pasos/llamadas (anti fan-out, $0-friendly con free-tiers).
- Contenido externo (de tools) sigue marcado **no confiable**; las acciones `high` siguen pidiendo confirmación.

## Reglas
- Python 3.12, async, type hints, docstrings breves.
- **Equipos data-driven** (config), no hard-code. Respeta Registry/interfaces/bóveda de secretos/tools del Prompt 6.

## No hagas todavía
- Memoria (grafo/vectores/Obsidian) → **Prompt 8**. Frontend/visual → Prompt 9.
- Proveedores OAuth reales (Google, SMTP) → futuro.

## Criterio de aceptación
- En stub: una tarea compleja se descompone, se reparte a las áreas correctas, una subtarea de gasto pasa por Finanzas, una consulta inter-agente respeta allowlist y el tope de hops, y el resultado se integra coherente.
- Tema desconocido → cae en Multifacético y queda logueado.
- Los topes (`max_subtareas`/`hops`/`model_calls`) cortan el fan-out.
- `pytest` pasa **offline** (modelos en stub).
- Actualiza `CLAUDE.md` §10 (Prompt 7 completo) y §11 (topes/allowlist inter-agente). Nota qué sigue → **Prompt 8 (Memoria: grafo + vectores + Obsidian)**.
