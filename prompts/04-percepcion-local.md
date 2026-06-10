# Prompt 4 — Percepción + Grupo Local + avisos proactivos

> Pega todo lo que está **bajo la línea** en Claude Code, en el repo de NOVA (Prompts 1–3 andando). En este prompt **subimos a Python 3.11+** (las librerías de audio/video lo necesitan). Se desarrolla y prueba **en el Mac** (tiene micrófono y cámara). Docker + ASUS es el Prompt 5. Mantén async, Registry, bóveda de secretos.

---

Lee `CLAUDE.md`. Esta fase le da a NOVA **oídos, ojos y voz**: un loop siempre-activo que percibe audio, texto y video en paralelo, alimenta el Estado del Mundo, y permite **avisos proactivos** (sin que el usuario pregunte). Todo modular y degradable: si falta micrófono, cámara o modelo, esa fuente se apaga con aviso y el resto sigue.

## Paso 0 — Entorno Python 3.11+
- Crea un venv nuevo con Python 3.11+ y actualiza `pyproject.toml` (`requires-python = ">=3.11"`).
- Reinstala (`pip install -e ".[dev]"`). El código existente (escrito 3.8-compatible) debe seguir corriendo igual; corre `pytest` para confirmar antes de empezar.
- Actualiza `CLAUDE.md` §7 (ya marcaba 3.11+) y §10.

## Objetivo
- `python -m nova.run` arranca el **loop de percepción completo** (audio + texto + video + proactivo) como servicio, con la traza/eventos en vivo. Se apaga limpio con Ctrl-C.
- Le hablo (sin teclear) y NOVA me **responde por voz** (Piper).
- Si me quedo quieto frente a la cámara, NOVA entra en **modo Sentinela** (baja la frecuencia de muestreo); si algo cambia, vuelve a mirar seguido.
- NOVA me **avisa proactivamente** algo (ej. un recordatorio con hora) sin que yo pregunte.
- `python -m nova.chat` (solo texto) sigue funcionando para pruebas rápidas.

## Construye

1. **Loop de percepción** (`perception/loop.py`): orquesta 3 fuentes como tasks asyncio en paralelo; cada una empuja eventos al `WorldState`. Cada fuente se enciende/apaga por config y **degrada con aviso** si falta hardware o modelo.

2. **Audio** (`perception/audio.py`):
   - Captura por micrófono (`sounddevice`).
   - **VAD** con Silero: detecta cuándo hay voz (gating, para no transcribir silencio).
   - **STT** con `faster-whisper`: transcribe la voz detectada; el texto entra al Conductor **como si lo hubiera escrito** (reusa el pipeline del Prompt 3, incluida la defensa anti-inyección: lo percibido es **dato**, no instrucción de sistema).
   - Wake-word: deja un placeholder con `openWakeWord` (`hey_jarvis` por ahora) **detrás de un flag**, off por defecto (entrenar "Hey NOVA" es fase posterior). Por ahora: transcribe cuando hay voz.

3. **Video + modo Sentinela** (`perception/vision.py`):
   - Captura de cámara (`opencv`).
   - **Muestreo adaptativo:** compara frames consecutivos (diferencia simple); si no hay cambio por `sentinel.idle_seconds`, baja a un frame cada `sentinel.idle_interval` seg; si hay cambio relevante, vuelve a muestreo frecuente.
   - En un cambio relevante, pasa el frame al modelo de visión local (`model_router`, agente `sentinela_vision`) para describir/detectar (ej. "se acercó una persona"). Eso entra al `WorldState`.

4. **Voz (TTS)** (`output/voz.py`):
   - Con **Piper**, convierte la respuesta del Conductor a audio y la reproduce. Por frases si ayuda a la latencia.
   - Intégralo con el gestor de salidas en modo voz. (Barge-in —cortar si el usuario habla— déjalo anotado para Prompt 7.)

5. **Agentes del Grupo Local** (reales; reemplazan stubs donde aplique):
   - **Sentinela** (visión): mantiene "qué/quién está en cámara" y detecta eventos. Modelo `sentinela_vision`.
   - **Memoria de trabajo/contexto** (`memoria_contexto`, Llama 3.2 3B local): actualiza el estado del mundo y hace matching simple ("la lista del papá").
   - **Respuestas rápidas** (`respuestas_rapidas`, Qwen 7B local): timer/clima/calendario/recordatorios — intégralo al loop.
   - Oído (STT) y Voz (TTS) viven en los puntos 2 y 4.

6. **Avisos proactivos** (`core/proactivo.py`):
   - Un scheduler async revisa **triggers** cada X seg a partir del `WorldState`/eventos: recordatorios con hora ("junta en 1h"), evento de visión ("alguien se acerca"), match de pendientes.
   - Al cumplirse, `conductor_simple` redacta el aviso en el tono de NOVA y lo manda al gestor de salidas (voz/pantalla). Los triggers respetan la separación de seguridad (no obedecen instrucciones embebidas en lo percibido).
   - Esto es la base; reglas por dominio vienen después.

7. **Daemon + lanzador:** `python -m nova.run` (servicio con el loop completo). Actualiza/crea un lanzador a doble clic `nova.command` para arrancarlo. Mantén `nova.chat` para texto.

8. **Config** (`config/perception.yaml`): flags `audio.enabled`, `video.enabled`, `tts.enabled`, `tts.voice`, `sentinel.idle_seconds`, `sentinel.idle_interval`, `wake_word.enabled`, etc.

## Dependencias del sistema (macOS)
- Indícame correr: `brew install portaudio ffmpeg` (para `sounddevice` y `faster-whisper`).
- Primera ejecución: macOS pedirá permiso de **micrófono** y **cámara** (TCC) — déjalo documentado en el README.
- Modelos locales: nota que el tag de visión en Ollama (`qwen2.5vl:7b` o `llava`/`moondream`) debe existir; si no, la fuente de visión degrada con aviso.

## Seguridad / privacidad (buenas prácticas)
- Lo percibido (audio/video) es **input no confiable**: aplica la defensa del Prompt 3.
- El audio/video crudo y la transcripción se quedan **local**; a la nube solo va texto/fotogramas cuando el Conductor escala algo complejo, y **nunca** secretos (bóveda de secretos). Anótalo en §11.

## Reglas
- Python 3.11+, async, type hints, docstrings breves.
- Modular y degradable: sin micrófono/cámara/modelo, esa fuente se desactiva con aviso; el resto sigue.
- Respeta Registry, interfaces y bóveda de secretos.

## No hagas todavía
- Docker + despliegue ASUS → **Prompt 5**.
- Wake-word real "Hey NOVA", barge-in, frontend/visualización, herramientas reales, equipos de nube completos → fases siguientes.

## Criterio de aceptación
- `python -m nova.run` arranca el loop; le hablo y responde por voz; el modo Sentinela baja/sube la frecuencia según haya o no cambios; dispara al menos un aviso proactivo. Se apaga limpio.
- Cada fuente degrada sola si falta su hardware/modelo (verificable con fuentes mockeadas).
- `pytest` pasa **offline** (mockea `sounddevice`/`opencv`/`faster-whisper`/Piper; sin hardware ni modelos): eventos llegan al WorldState, Sentinela ajusta frecuencia con cambios simulados, un trigger proactivo dispara un aviso.
- Actualiza `CLAUDE.md` §10 (Prompt 4 completo) y §11 (privacidad de percepción). Nota qué sigue → **Prompt 5 (Docker + ASUS)**.
