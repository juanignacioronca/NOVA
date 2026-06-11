# NOVA — frontend (capa visual)

NOVA **audio-reactiva** (Three.js) + **vista de flujo en vivo** (TraceEvents reales)
+ **pantalla con contenido dinámico** + **botones de modalidad**. Vite + TypeScript.

> Corre **local** contra el backend local (Vite proxea `/ws` y `/tts` a `:8000`).
> PWA / multi-dispositivo / despliegue = Prompt 11.

## Uso (dev)

```bash
# 1) backend (en la raíz del repo, con el venv)
python -m nova.app            # escucha en :8000

# 2) frontend (en frontend/)
npm install
npm run dev                   # http://localhost:5173  (proxea al backend)
```

Hablale/escribile: NOVA se mueve con su voz (si Piper está instalado en el backend;
si no, usa un envolvente sintético), la pantalla muestra el resultado como contenido
dinámico, y el toggle **flujo en vivo** enciende los nodos con los eventos reales.

## Build

```bash
npm run build                 # tsc --noEmit && vite build  → dist/
npm run preview               # sirve dist/ localmente
```

## Identidad visual
HUD oscuro (`#070b15`), Chakra Petch + IBM Plex Mono, paleta cyan/mint/amber/violet/slate.
