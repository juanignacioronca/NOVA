# NOVA

Asistente personal multiagente (tipo Jarvis): **simple en local, complejo en la nube**,
con un único **Conductor** que entiende, orquesta y responde — ahora con **oídos,
ojos y voz** (loop de percepción siempre-activo) y **avisos proactivos**. Objetivo
de diseño: máxima capacidad con gasto **$0**. La fuente de verdad es [CLAUDE.md](CLAUDE.md).

> **Estado:** Prompt 4 — Percepción + Grupo Local. Loop siempre-activo (audio +
> texto + video) que alimenta el Estado del Mundo, responde por voz (Piper),
> modo **Sentinela** (muestreo de cámara adaptativo) y **avisos proactivos**.
> Todo **modular y degradable**: sin micrófono/cámara/modelo, esa fuente se apaga
> con aviso y el resto sigue. El núcleo (texto) funciona sin claves ni modelos.

## Requisitos

- **Python 3.11+** (desde Prompt 4; lo piden las libs de audio/video). El núcleo
  sigue corriendo sin claves ni Ollama (modo stub).
- Para la percepción real (voz/mic/cámara), dependencias de sistema en macOS:
  ```bash
  brew install python@3.12 portaudio ffmpeg
  ```

## Instalación

```bash
# 1) venv con Python 3.11+ (acá usamos el de Homebrew)
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate

# 2) núcleo (texto) — suficiente para nova.cli / nova.chat / pytest
pip install -e ".[dev]"

# 3) (opcional) stack de percepción real: audio + video + voz
pip install -e ".[perception]"

cp .env.example .env          # opcional: completá claves cuando las tengas
```

### Modelos / voces locales (para la percepción real)
- **Ollama** (visión Sentinela): `ollama pull qwen2.5vl:7b` (o `llava`/`moondream`).
  Si el tag no existe, la visión degrada con aviso.
- **Voz Piper**: descargá un modelo `.onnx` (ej. `es_ES-davefx-medium`) y dejalo en
  `~/.local/share/piper/` (o exportá `NOVA_PIPER_DIR`). Si falta, NOVA responde por pantalla.

### Permisos de macOS (TCC)
La primera vez, macOS pedirá permiso de **micrófono** y **cámara**. Si lo negaste,
habilitalo en *Ajustes → Privacidad y seguridad → Micrófono / Cámara* para tu terminal.

## Uso

```bash
python -m nova.run     # daemon: loop de percepción completo (audio+texto+video+proactivo)
python -m nova.chat    # chat por texto (prueba rápida; /img <ruta> <texto> para imágenes)
python -m nova.doctor  # estado de proveedores de modelos + modelos de Ollama
```

`nova.run` arranca el loop, muestra la traza en vivo, te escucha y responde por voz;
entra en **Sentinela** si no hay cambios en cámara y dispara **avisos proactivos**
(ej. un recordatorio). Se apaga limpio con **Ctrl-C**. A doble clic: `nova.command`
(daemon), `run-nova.command` (chat), `doctor.command`. *(1ª vez en macOS: clic
derecho → Abrir.)*

## Tests

```bash
pytest        # offline: mockea hardware/modelos; sin red ni claves
```

## Arquitectura (resumen)

```
 [audio · texto · video]  → loop de percepción (degradable) → Estado del Mundo
        (mic→VAD→STT)         (video: modo Sentinela)              │
                                                                   ▼
                              Conductor (comprende · clasifica · sintetiza)
                                ├── simple   → Grupo Local
                                └── complejo → Grupo Nube (PMO → Estrategia)
                              → voz (Piper) + pantalla · avisos proactivos
```

Detalle en [CLAUDE.md](CLAUDE.md). Roster de modelos en
[src/nova/config/models.yaml](src/nova/config/models.yaml); flags de percepción en
[src/nova/config/perception.yaml](src/nova/config/perception.yaml).
