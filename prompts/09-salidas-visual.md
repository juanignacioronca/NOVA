# Prompt 9 — Salidas + capa visual

> Pega todo lo que está **bajo la línea** en Claude Code, en el repo de NOVA (Prompts 1–8 andando, Python 3.12, en el Mac). El frontend es Vite + TypeScript + Three.js, corre local (Vite dev → backend local). El empaque PWA / multi-dispositivo / despliegue es **Prompt 11**. Mantén la bóveda de secretos.

---

Lee `CLAUDE.md`. Esta fase le da a NOVA su **capa visual y de salida**: una NOVA **audio-reactiva** que se mueve con su voz, la **vista de flujo en vivo** (el diagrama, pero con lo que está pasando de verdad), una **pantalla con contenido dinámico**, y los **botones de modalidad**. Reusa la **identidad visual que ya tiene NOVA** en los diagramas del proyecto (continuidad).

## Identidad visual (reusar — ya es la de NOVA)
- Fondo HUD oscuro (`#070b15`), tipografías **Chakra Petch** (títulos) + **IBM Plex Mono** (etiquetas).
- Paleta: `--cyan #37d0ea` (núcleo) · `--mint #49e6a6` (local) · `--amber #ffb454` (nube) · `--violet #b48cff` (memoria/transversales) · `--slate #8595b0` (auditoría).
- Detalles: corner-ticks, glows suaves, badges mono. (Como en el simulador y el árbol de agentes.)

## Objetivo
- Le hablo y veo a **NOVA pulsar/morfear con las ondas de su voz** (audio-reactiva).
- Puedo abrir la **vista de flujo en vivo**: los nodos (Percepción → Conductor → Local | Empresa con sus sub-agentes → Salidas, + Memoria + Herramientas) **se encienden con los `TraceEvent` reales** mientras NOVA trabaja — es el simulador, pero de verdad.
- Los **resultados** se muestran como **contenido dinámico** (tarjetas/tablas/itinerario), no solo texto.
- Tres **botones de modalidad**: Solo voz / Solo pantalla / Ambos (manual, los prendo yo).

## Construye

1. **Frontend** (`frontend/`, Vite + TypeScript): se conecta al backend por `WS /ws` (consume el stream de `TraceEvent` + respuestas + payloads). Aplica la identidad visual de arriba.

2. **NOVA audio-reactiva** (`frontend/src/nova/`): una visualización **Three.js** (esfera/partículas tipo supernova) que reacciona a la voz de NOVA vía **Web Audio API `AnalyserNode`** sobre el audio TTS que llega del backend → amplitud/frecuencia mueven la forma. Estado idle en silencio, activo al hablar. Es la pieza central.

3. **Vista de flujo en vivo** (`frontend/src/flow/`): replica el layout del **simulador** (Percepción → Conductor [Comprensión+Orquestación] → Núcleo Local | Empresa [sub-agentes] → Salidas; + Memoria + Herramientas; Auditoría al costado), pero **data-driven desde los `TraceEvent` reales** por WS: cada nodo se enciende cuando su agente actúa, con la traza en vivo al lado. Toggle para mostrar/ocultar.

4. **Pantalla con contenido dinámico** (`frontend/src/screen/`): el área de resultados renderiza una **presentación estructurada** (proceso + resultado) que manda el backend — tarjetas, tablas, itinerario, etc. (no solo texto).

5. **Botones de modalidad** (UI): Solo voz / Solo pantalla / Ambos. Manual. La selección va al backend; reusa el gestor de salidas del Prompt 4 (voz narra/resume · pantalla muestra proceso + detalle; complementarios o se suplen).

6. **Soporte en el backend:**
   - **Audio TTS al cliente:** Piper genera en el backend y **streamea el audio al navegador** (chunks por WS o endpoint), que lo reproduce **y** lo alimenta al `AnalyserNode`. (La voz pasa a sonar en el dispositivo → sirve para multi-dispositivo y para la viz.)
   - **Voz streaming + barge-in:** TTS por frases (menor latencia); barge-in = si el VAD del cliente detecta que hablo mientras NOVA habla, manda "stop" y se corta la reproducción. (Barge-in básico está bien.)
   - **Payload de presentación:** el gestor de salidas emite `{proceso (traza), resultado (contenido dinámico), modalidad}` que el frontend renderiza.

7. **Robustez:** el frontend degrada si el backend no responde; corre local (Vite dev + backend local). Sin PWA/multi-dispositivo aún.

## Reglas
- Frontend Vite + TS + Three.js, identidad visual de NOVA. Backend Python 3.12, async.
- Respeta el contrato del `WS /ws` y el stream de `TraceEvent` (Prompts 3/5). Bóveda de secretos.

## No hagas todavía
- PWA, multi-dispositivo, Tailscale, mkcert, wake word, despliegue ASUS → **Prompt 11**.
- Reconocimiento de personas (cara/voz) → **Prompt 10**.

## Criterio de aceptación
- Frontend buildea (`npm run build`) y corre en local contra el backend.
- NOVA se mueve con su voz (audio-reactiva); la vista de flujo en vivo enciende nodos con `TraceEvent` reales; los resultados salen como contenido dinámico; los 3 botones de modalidad funcionan.
- Backend: tests de los payloads/streaming offline; `pytest` verde.
- Actualiza `CLAUDE.md` §10 (Prompt 9 completo). Nota qué sigue → **Prompt 10 (Reconocimiento de personas: cara + voz)**.
