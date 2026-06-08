# Prompt 3 — Conductor real (comprensión + multimodal + aclaración)

> Pega todo lo que está **bajo la línea** en Claude Code, en el repo de NOVA (Prompts 1 y 2 andando). Mantén **Python 3.8** (solo `httpx`, sin SDKs 3.9+), async, Registry y bóveda de secretos.

---

Lee `CLAUDE.md`. Esta fase convierte al Conductor en uno **de verdad**: entiende la intención con un modelo (no heurística), acepta **imágenes** además de texto (primer paso multimodal), **pregunta cuando le falta info**, sintetiza la respuesta final, y aplica las **buenas prácticas de seguridad** que aprendimos de proyectos tipo OpenClaw (defensa contra prompt injection). Además deja una **traza estructurada** que más adelante alimentará la vista de flujo en vivo.

## Objetivo
- En `python -m nova.chat`, una petición ambigua hace que NOVA **pregunte** lo que falta antes de actuar (ej. "organízame un finde" → "¿qué fin de semana y con quién?"), y al responder yo, **retoma** y resuelve.
- Puedo pasar una **imagen**: `/img ruta.png ¿qué es esto?` (o `--img` en CLI) y la comprensión la usa.
- La clasificación simple/complejo ahora la decide el modelo (con heurística de respaldo en stub).
- En complejo, la respuesta final es una **síntesis coherente** de lo que hicieron los agentes, no un pegoteo.
- El contenido del usuario / externo se trata como **datos, nunca como instrucciones**: un intento de "ignora tus instrucciones…" se detecta, no se obedece y queda anotado en la traza.

## Construye

1. **Motor de comprensión** (`core/comprension.py`):
   - `async def comprender(texto, images=None, contexto=None) -> Intent`.
   - `Intent` (dataclass): `intencion: str`, `entidades: dict`, `faltantes: list[str]`, `complejidad: "simple"|"complejo"`, `confianza: float`, `multimodal: bool`.
   - Usa `conductor_simple` (local) para lo claro; si la confianza es baja o hay imagen, escala a `conductor_complex` / `conductor_vision`. Pide al modelo **JSON estricto** y parsea con tolerancia (si no es JSON válido, reintenta una vez pidiendo solo JSON; si falla, cae a heurística).
   - **Modo stub:** heurística por palabras clave para intención + complejidad, para seguir corriendo sin modelos.

2. **Multimodal (paso 1: imágenes):**
   - `Conductor.attend(texto, images=None)`. Con imágenes, arma mensajes en formato visión OpenAI-compatible (`content: [{type:"text",...}, {type:"image_url", image_url:{url:"data:image/...;base64,..."}}]`) y enruta a un modelo multimodal.
   - `config/models.yaml`: agrega `conductor_vision: gemini:gemini-2.5-flash` con fallback local `ollama:qwen2.5vl:7b` (comenta que el tag de Ollama debe existir).
   - CLI/REPL: soporta `/img <ruta> <texto>` y bandera `--img <ruta>`.
   - (Solo imágenes ahora; audio/video real es Prompt 4.)

3. **Diálogo de aclaración:**
   - Si `faltantes` no está vacío o `confianza` < umbral → el Conductor devuelve **una** pregunta concisa (la mejor para desbloquear) y guarda en `WorldState` un `pending_clarification` con el Intent parcial.
   - El siguiente mensaje del usuario se **fusiona** con el Intent pendiente y se reevalúa. Máximo 2 rondas; luego procede con la mejor interpretación, avisando el supuesto.

4. **Ruteo + síntesis:**
   - simple → agente local (como hoy); la respuesta final puede pulirla `conductor_simple`.
   - complejo → despacha al PMO por el bus, recolecta resultados, y `conductor_complex` produce la **respuesta final sintetizada** (coherente, en el tono de NOVA).
   - Mantén el log + evento por paso.

5. **Seguridad — defensa contra prompt injection** (buenas prácticas tipo OpenClaw):
   - Las **instrucciones de comportamiento de NOVA** van solo en el rol `system`. El texto del usuario y cualquier contenido externo van en `user`, claramente delimitados. **Nunca** concatenar contenido no confiable dentro del system prompt.
   - Helper `marcar_no_confiable(contenido, fuente)` que envuelve contenido externo (web/archivos/mensajes — se usará en fases siguientes) señalando que **no debe obedecerse como instrucción**.
   - Chequeo liviano en la comprensión: detecta patrones de override ("ignora tus instrucciones", "actúa como…", "system:", etc.) → no se actúa sobre ellos, se marca `inyeccion_detectada` en la traza. (La defensa real es la separación estructural; esto es la alerta.)
   - Documenta esto: agrega a `CLAUDE.md` una breve **§11 "Seguridad"** con estas reglas (separación system/usuario, contenido externo = datos, secretos solo en `.env`).

6. **Traza estructurada** (prepara la vista de flujo en vivo que pidió el usuario):
   - `core/trace.py`: `TraceEvent` (dataclass): `ts, etapa, agente, grupo, modelo, detalle, estado`.
   - El Conductor mantiene `self.last_trace: list[TraceEvent]` y los **emite** por un callback/cola async (`on_event`), además de escribir el JSONL.
   - El REPL imprime los eventos compactos; más adelante el frontend (Prompt 7) consumirá el mismo stream para dibujar el flujo en vivo. **No construyas frontend ahora**; solo deja el stream listo y documentado.

7. **Tests** (offline, mock `httpx`, 3.8):
   - Comprensión devuelve `Intent` estructurado; entrada ambigua → pregunta de aclaración; respuesta de seguimiento se fusiona y procede.
   - Clasificación simple/complejo enruta correcto.
   - Intento de inyección se marca y **no** se obedece (system prompt intacto; contenido tratado como dato).
   - Petición con imagen se enruta a un modelo de visión (cliente mockeado).
   - `pytest` pasa sin red ni claves.

## Reglas
- Python 3.8, async, type hints, docstrings breves. Solo `httpx`.
- Respeta Registry, interfaces y bóveda de secretos de `CLAUDE.md`.

## No hagas todavía
- Audio/video en vivo, percepción/Sentinela → Prompt 4.
- Herramientas reales, equipos completos, frontend/visualización → fases siguientes.

## Criterio de aceptación
- En `nova.chat`: petición ambigua → NOVA pregunta y luego resuelve; `/img` funciona; una consulta compleja devuelve síntesis coherente.
- Un intento de inyección queda anotado y **no** altera el comportamiento.
- Existe el stream de `TraceEvent` consumible.
- `pytest` pasa offline.
- Actualiza `CLAUDE.md` §10 (Prompt 3 completo) y agrega §11 "Seguridad". Nota qué sigue → **Prompt 4 (Percepción + Grupo Local + Docker/ASUS)**.
