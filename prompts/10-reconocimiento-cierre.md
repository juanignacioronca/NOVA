# Prompt 10 — Reconocimiento de personas (cara + voz) + cierre del proyecto

> Pega todo lo que está **bajo la línea** en Claude Code, en el repo de NOVA (Prompts 1–9 andando, Python 3.12, en el Mac). **Es el último prompt:** agrega la última capacidad y deja NOVA cerrada y operable. Las libs pesadas con **import perezoso + stub** (tests offline). Los biométricos van **estrictamente locales**. Mantén async, Registry, bóveda de secretos.

---

Lee `CLAUDE.md`. Esta fase hace dos cosas: **(A)** NOVA reconoce **quién** se le acerca (cara) y **quién** le habla (voz), y **(B)** cierra el proyecto con un smoke end-to-end, un documento de operación y los prompts de auditoría.

---

## PARTE A — Reconocimiento de personas

> Clave de diseño: **no se entrena un modelo propio**. Se usan **embeddings** de modelos ya entrenados — la cara/voz se vuelve un vector, se "enrola" a la persona con pocas muestras, y al runtime se compara por **coseno**. Se guarda en la **memoria del Prompt 8** (los nodos ya tienen embeddings). Es como Face ID en concepto, sin GPU ni `.h5`.

### Construye

1. **Cara** (`recognition/faces.py`):
   - **Detector + embedder** con modelo pre-entrenado: usa **InsightFace/ArcFace** (onnxruntime-cpu, 512-d) como primario; `face_recognition`/dlib (128-d) como alternativa. Import perezoso + **stub determinista** (vector derivado de los bytes) para tests offline.
   - **Enrolar**: desde una carpeta de fotos de la persona (`personas/<nombre>/fotos/`), detecta+embeb cada foto, **promedia** los vectores y guarda el vector facial en el **nodo de esa persona en la memoria** (5–20 fotos bastan; más = más robusto).
   - **Match en runtime**: dada una cara de un fotograma del Sentinela, la embeb y compara por coseno contra los enrolados → **nombre + confianza**; bajo umbral → "desconocido".

2. **Voz** (`recognition/voices.py`):
   - **Speaker embeddings** pre-entrenados: **Resemblyzer** (simple) o **SpeechBrain ECAPA-TDNN** (más preciso). Import perezoso + **stub determinista**.
   - **Enrolar**: desde unas muestras de voz (`personas/<nombre>/voz/`), embeb+promedia → guarda el vector de voz en el nodo de la persona.
   - **Match en runtime**: una locución del pipeline de audio (Prompt 4) → embeb → coseno contra enrolados → nombre. Combinado con la cara da más confianza.

3. **Enrolamiento (CLI)** (`enroll.py`): `python -m nova.enroll <nombre> --fotos <carpeta> [--voz <carpeta>]` → crea/actualiza el nodo de la persona en la memoria con sus vectores cara/voz.

4. **Integración**: el **Sentinela** (Prompt 4) detecta cara → match → identidad; el **Oído** (Prompt 4) etiqueta quién habla; la **memoria** (Prompt 8) liga la persona a sus pendientes; el **proactivo** (Prompt 4) hace real el ejemplo: *"se acerca [nombre]; probablemente por [tarea pendiente]"* (detecta → embedding → match → jala pendientes de la memoria).

5. **Privacidad (biométrico)**: cara y voz son datos sensibles → **solo locales** (en la memoria local, **nunca** a la nube; calza con la bóveda), enrolar solo a quien tú quieras, y un modo fácil de **borrar** los biométricos de una persona.

---

## PARTE B — Cierre del proyecto

1. **Smoke end-to-end** (`scripts/smoke_e2e.py`): ejercita la cadena completa en stub — percepción → Conductor → (Local + Empresa) → herramientas → memoria → reconocimiento → payload de presentación — y verifica que todo enlaza. Es la "revisión total" en versión liviana.

2. **HANDOFF.md** (operar NOVA): cómo correr cada cosa (backend `python -m nova.app`, frontend `npm run dev` o `npm run build`→servir `dist/` estático en producción, daemon `run.py`, enrolar personas), **desplegar en el ASUS** (apunta a los artefactos Docker del Prompt 5; build de la imagen en x86_64+GPU), la **estrategia de modelos** ($0), y la **postura de seguridad** (§11). Un solo doc "esto es NOVA y así se opera".

3. **Auditoría asíncrona** (`auditoria/*.md`): los prompts fijos que corres tú en Claude Code + Opus para leer los registros JSONL y **proponer mejoras / nuevos equipos** (que apruebas e implementas editando `teams.yaml`). Cierra el lazo de mejora continua, fuera del flujo en vivo.

4. **Opcional futuro** (solo deja anotado, **no** lo construyas): multi-dispositivo / PWA, acceso remoto Tailscale, wake word. NOVA queda **100% funcional en local + LAN** sin esto.

---

## Reglas
- Python 3.12, async, type hints, docstrings breves. Libs pesadas (insightface/onnxruntime, dlib, resemblyzer, speechbrain) con **import perezoso + stub** → `pytest` corre sin hardware ni modelos.
- Reusa la **memoria del Prompt 8** para guardar los vectores; respeta Registry/interfaces/bóveda/tools.

## No hagas todavía
- Multi-dispositivo, PWA, Tailscale, wake word (opcional futuro).
- **Nunca** subir biométricos a servicios externos.

## Criterio de aceptación
- Enrolar a una persona (fotos y/o voz) guarda sus vectores en su **nodo de memoria**; el match identifica correctamente sobre el umbral y devuelve "desconocido" bajo el umbral (con embedders stub deterministas offline).
- El ejemplo "se acerca [nombre] + sus pendientes" corre en stub (detecta → match → memoria → aviso proactivo).
- `scripts/smoke_e2e.py` pasa la cadena completa; existen `HANDOFF.md` y los prompts en `auditoria/`.
- `pytest` pasa **offline** (sin red, modelos ni cámara/mic).
- Actualiza `CLAUDE.md` §10 (Prompt 10 completo) y §11 (biométricos locales). Marca el **roadmap como terminado** y deja anotado el opcional futuro.
