# NOVA v2.0 — Roadmap de prompts

Cada prompt = **una sesión de Claude Code**, una fase coherente. Claude Code lee `CLAUDE.md` al inicio de cada una. Vamos en orden; cada fase deja tests y actualiza la §10 de `CLAUDE.md`. Yo (Claude, en este chat) te entrego cada prompt en detalle cuando llegues a él.

| # | Prompt | Qué construye | Estado |
|---|---|---|---|
| **1** | **Esqueleto del núcleo** | Scaffold + capa de modelos (con modo stub) + Registry + BaseAgent + MessageBus + WorldState + Conductor (comprensión+ruteo+respuesta) + registro JSONL + CLI + tests. Corre con texto, sin claves. | ✅ listo → `prompts/01-esqueleto.md` |
| 2 | Capa de modelos real | Conectar Ollama local + Gemini/Groq/OpenRouter con claves reales; probar `complete()` de verdad; 429 + backoff + fallback; repartir carga entre proveedores. | pendiente |
| 3 | Conductor real | Comprensión robusta (texto → luego imágenes), clasificación de complejidad fiable, síntesis de respuesta y **diálogo de aclaración** (preguntar cuando falta info). | pendiente |
| 4 | Percepción + Grupo Local | Loop de audio (STT + VAD), texto y visión con **modo Sentinela**; TTS; agentes locales (respuestas rápidas, memoria/contexto, sentinela); avisos proactivos. | pendiente |
| 5 | Herramientas | Capa de tools entrada/salida (calendario, clima, búsqueda web, mapas, etc.) registradas en el Registry; permisos; uso desde los agentes. | pendiente |
| 6 | Grupo Nube | PMO real + transversales (Estrategia, Finanzas) + áreas con sus sub-agentes; **skills inter-agente**; flujo de proyecto completo (ej. el finde de trekking). | pendiente |
| 7 | Salidas multimodales | Voz (TTS streaming + barge-in) + pantalla (**HTML dinámico** con proceso y resultados) + **botones de modalidad** (solo voz / solo pantalla / ambos). | pendiente |
| 8 | Memoria | Grafo + vectores (Qdrant u opción liviana) + capa **Obsidian** (markdown navegable); integración con el WorldState (caché vivo) y los registros. | pendiente |
| 9 | Auditoría asíncrona | Formato de registros consolidado + los **prompts fijos** de `audit/prompts/` para correr en Claude Code + Opus 4.8: detectar patrones y proponer mejoras / nuevos equipos. | pendiente |
| 10 | Frontend / PWA | Visualización (supernova), app con los botones, multi-dispositivo (mkcert LAN, Tailscale remoto) y wake word **"Hey NOVA"**. | pendiente |

> El orden puede ajustarse. La idea es siempre: una fase, que corra y tenga tests, antes de pasar a la siguiente.
