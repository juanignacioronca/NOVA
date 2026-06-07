# NOVA

Asistente personal multiagente (tipo Jarvis): **simple en local, complejo en la nube**,
con un único **Conductor** que entiende, orquesta y responde. Objetivo de diseño:
máxima capacidad con gasto **$0**. La fuente de verdad del proyecto es
[CLAUDE.md](CLAUDE.md).

> **Estado:** Prompt 1 — esqueleto del núcleo. Corre de punta a punta con texto,
> rutea por complejidad (local vs nube) y deja registro en `logs/`. Sin audio,
> video, frontend ni herramientas reales todavía (stubs). **Funciona sin claves
> ni modelos** (modo stub).

## Requisitos

- Python 3.11+ es el target del proyecto; el esqueleto es compatible con 3.8+.
- No necesitás claves ni Ollama para probar el esqueleto (modo stub automático).

## Instalación

```bash
pip install -e ".[dev]"     # instala nova + httpx, pyyaml, pytest, pytest-asyncio
cp .env.example .env        # opcional: completá claves cuando las tengas
```

## Uso

```bash
python -m nova.cli "ponme un timer de 10 minutos"     # simple → núcleo local
python -m nova.cli "organízame un finde de trekking"   # complejo → nube (PMO)
```

Cada corrida imprime la traza (intención, complejidad, agentes que intervinieron,
respuesta final) y la ruta del registro JSONL escrito en `logs/`.

## Tests

```bash
pytest
```

## Arquitectura (resumen)

```
texto → Conductor (comprende + clasifica complejidad)
          ├── simple   → Grupo Local  (RespuestasRapidas)
          └── complejo → Grupo Nube   (PMO → Estrategia, vía MessageBus)
        → respuesta final + registro JSONL en logs/
```

Detalle completo en [CLAUDE.md](CLAUDE.md). El mapa agente→modelo vive en
[src/nova/config/models.yaml](src/nova/config/models.yaml).
