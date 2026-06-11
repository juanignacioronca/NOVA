# Prompt 8 — Memoria (grafo + vectores + Obsidian)

> Pega todo lo que está **bajo la línea** en Claude Code, en el repo de NOVA (Prompts 1–7 andando, Python 3.12, en el Mac). Probable en stub/offline. **Todo local y $0.** Mantén async, Registry, bóveda de secretos.

---

Lee `CLAUDE.md`. Esta fase le da **memoria de largo plazo** a NOVA: dos capas — un **motor local (grafo + vectores)** para consultas rápidas, y una **capa Obsidian** (markdown navegable por humano) que la espeja. El `WorldState` sigue siendo el **caché vivo** de esta memoria. Todo local, sin servicios pagos.

## Objetivo
- NOVA **extrae y guarda** entidades (personas, proyectos, eventos, lugares, tareas, hechos) y sus relaciones desde las conversaciones y los registros.
- NOVA **recuerda**: por similitud semántica (vectores) y por relaciones (grafo, multi-hop). Ej.: si antes dijiste "prefiero dificultad media", el Conductor lo recupera para el próximo plan de cerro; "la lista del papá" queda como tarea ligada a la entidad Papá.
- Hay una **bóveda Obsidian** (carpeta de `.md` con `[[wikilinks]]`) que puedo abrir y navegar; NOVA la mantiene sincronizada.

## Construye

1. **Motor de memoria** (`memory/store.py`, SQLite, un solo archivo):
   - Tabla `nodos` (entidades: `id, tipo, nombre, props(JSON), ts`).
   - Tabla `aristas` (relaciones: `src, dst, tipo, props, ts`) → el grafo.
   - Vectores: guarda el embedding por nodo/hecho como blob; búsqueda por **coseno con numpy** (a escala personal alcanza de sobra; deja anotado que `sqlite-vec`/Qdrant son optimización futura para escala). **Sin servicios externos.**
   - API: `add_nodo`, `add_arista`, `buscar_semantico(q, k)`, `vecinos(nodo, tipo?)`, `multi_hop(nodo, profundidad)`, `actualizar`, `eliminar`.

2. **Embeddings** (`memory/embeddings.py`): locales vía Ollama (`nomic-embed-text`), con **fallback stub determinista** para offline/tests.

3. **Grafo** (`memory/graph.py`): carga las aristas en `networkx` para traversal/multi-hop y consultas de relación.

4. **Extractor** (`memory/extractor.py`): desde un turno de conversación / registro, un modelo extrae entidades + relaciones + hechos (JSON, parseo tolerante, **heurística stub** de respaldo) y escribe al store + crea/actualiza las notas Obsidian. Acota el tamaño de lo extraído.

5. **Capa Obsidian** (`memory/obsidian.py`): una bóveda (carpeta configurable, ej. `memoria/vault/`); **una nota `.md` por entidad** con frontmatter + `[[wikilinks]]` a las entidades relacionadas (la estructura de links espeja el grafo). NOVA escribe las notas desde el store; deja la opción de re-ingerir ediciones del humano. Navegable en Obsidian.

6. **Integración:**
   - En la **comprensión**, el Conductor consulta la memoria (semántico sobre la consulta + vecinos de las entidades mencionadas) y carga ese contexto en el `WorldState` (el caché vivo). Esto hace funcionar "¿y las de China?", "prefieres dificultad media", "la lista del papá".
   - **Tool de memoria** (`buscar_memoria` / `recordar`) registrada con permisos (el agente local `memoria_contexto` la usa; otros según allowlist).
   - Tras cada petición, **extrae y persiste** lo nuevo (hechos, tareas, preferencias) ligado a sus entidades.

7. **Privacidad / $0:** memoria **solo local**; **nunca** guardar claves/credenciales en el store ni en las notas (bóveda de secretos). El contenido externo (de tools) sigue marcado **no confiable** antes de extraer.

## Reglas
- Python 3.12, async, type hints, docstrings breves. **Todo local, $0** (numpy + SQLite + Ollama embeddings + markdown).
- Respeta Registry/interfaces/bóveda de secretos/tools del Prompt 6.

## No hagas todavía
- Frontend/visual (vista de flujo en vivo, NOVA audio-reactiva) → **Prompt 9**.
- `sqlite-vec`/Qdrant a escala, re-ingesta avanzada de ediciones → futuro.

## Criterio de aceptación
- Se pueden agregar nodos/aristas; `buscar_semantico` trae lo relevante (con embeddings stub deterministas offline); `multi_hop` recorre relaciones.
- El extractor saca entidades/relaciones de un turno (stub heurístico) y genera notas `.md` con `[[wikilinks]]`.
- Una preferencia guardada ("dificultad media") se recupera en una consulta posterior; "la lista del papá" queda ligada a la entidad Papá.
- La tool de memoria respeta permisos.
- `pytest` pasa **offline** (sin red ni modelos).
- Actualiza `CLAUDE.md` §10 (Prompt 8 completo) y §11 (memoria local/privacidad). Nota qué sigue → **Prompt 9 (Salidas + visual)**.
