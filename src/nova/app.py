"""Servicio NOVA (FastAPI + WebSocket).

Envuelve el Conductor como backend alcanzable en la LAN:
- `GET /health`  → estado del servicio.
- `POST /chat`   → texto → respuesta + traza (one-shot).
- `WS  /ws`      → streamea la traza (`TraceEvent`) en vivo + la respuesta final.
- `GET /`        → página mínima (HTML/JS inline, sin dependencias) para hablarle
                   desde el navegador del teléfono/iPad/Mac.

Seguridad: pensado para la **LAN, nunca WAN** (el binding a la LAN se hace en el
compose; ver deploy/README.md). Claves solo por entorno (.env en runtime).

Concurrencia: cada request usa su propio Conductor (registry/bus aislados) y
comparte un único WorldState para continuidad (recordatorios, aclaraciones).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from .config_api import router as config_router
from .models import model_router
from .core.conductor import Conductor
from .core.trace import EventCallback
from .core.world_state import WorldState
from .env import load_env
from .logging.registro import Registro
from .output.presentacion import construir_presentacion
from .output.voz import VozTTS, frases
from .paths import PROJECT_ROOT

load_env()  # claves desde .env si existe (en Docker llegan por env_file)

app = FastAPI(title="NOVA", version=__version__)
app.include_router(config_router)

# CORS para el frontend en dev (Vite en :5173). En prod va detrás de la LAN.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.environ.get("NOVA_CORS", "*").split(",") if o] or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Estado compartido del servicio (un solo mundo; conductores por request).
_world = WorldState()
_registro = Registro()
_tts_cache: object = None  # VozTTS | False | None (lazy)


def _make_conductor(on_event: Optional[EventCallback] = None) -> Conductor:
    return Conductor(world=_world, registro=_registro, on_event=on_event)


async def _get_tts() -> Optional[VozTTS]:
    """VozTTS lazy: None si Piper/voz no están (el cliente degrada sin audio)."""
    global _tts_cache
    if _tts_cache is None:
        from .perception.config import load_perception_config

        voz = VozTTS(load_perception_config().tts.voice)
        _tts_cache = voz if await voz.start() else False
    return _tts_cache or None


# --- Centinela (visión por cámara): describe un frame cuando algo cambia ---
async def describir_frame(dataurl: str) -> str:
    """Describe una foto de la cámara con el modelo de visión local (sentinela_vision)."""
    from .core import prompts

    messages = [
        {"role": "system", "content": prompts.get("sentinela")},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "¿Qué ves en la cámara?"},
                {"type": "image_url", "image_url": {"url": dataurl}},
            ],
        },
    ]
    comp = await model_router.complete_meta("sentinela_vision", messages)
    return (comp.text or "").strip()


class ChatIn(BaseModel):
    text: str


class ChatOut(BaseModel):
    answer: str
    route: str
    model: str
    intent: str
    complexity: str
    trace: list


@app.get("/health")
async def health() -> dict:
    eventos = await _world.events()
    return {"status": "ok", "service": "nova", "version": __version__, "world_events": len(eventos)}


@app.post("/chat", response_model=ChatOut)
async def chat(body: ChatIn) -> ChatOut:
    eventos: list = []
    conductor = _make_conductor(on_event=lambda ev: eventos.append(ev.to_dict()))
    answer = await conductor.attend(body.text)
    run = conductor.last_run
    return ChatOut(
        answer=answer,
        route=run["route"],
        model=run["model"],
        intent=run["intent"],
        complexity=run["complexity"],
        trace=eventos,
    )


def _parse_msg(raw: str) -> dict:
    """Mensaje del cliente: JSON `{type,...}` o texto plano = un turno."""
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("type"):
            return data
    except (json.JSONDecodeError, ValueError):
        pass
    return {"type": "text", "text": raw}


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await websocket.accept()
    modalidad = "ambos"  # estado por conexión (Solo voz / Solo pantalla / Ambos)
    ultimo_frame = 0.0  # enfriamiento del centinela (protege la GPU de 6 GB)
    try:
        while True:
            msg = _parse_msg(await websocket.receive_text())
            tipo = msg.get("type")

            if tipo == "modalidad":
                modalidad = msg.get("value", "ambos")
                await websocket.send_json({"type": "modalidad", "value": modalidad})
                continue
            if tipo == "stop":  # barge-in: el cliente cortó la voz
                await websocket.send_json({"type": "stopped"})
                continue
            if tipo == "frame":  # centinela: la cámara detectó un cambio → mirar
                ahora = time.monotonic()
                img = msg.get("image", "")
                if ahora - ultimo_frame < 12 or not isinstance(img, str) or not img.startswith("data:"):
                    continue
                ultimo_frame = ahora
                try:
                    desc = await describir_frame(img)
                except Exception:
                    continue
                low = desc.lower()
                if not desc or low.startswith("nada") or low.startswith("[stub"):
                    await websocket.send_json({"type": "sentinela", "detalle": "sin novedad"})
                    continue
                await websocket.send_json({
                    "type": "presentacion", "modalidad": modalidad, "texto": desc, "voz": desc,
                    "proceso": [], "meta": {"route": "centinela", "model": "sentinela_vision"},
                    "resultado": {"tipo": "tarjeta", "titulo": "Centinela", "texto": desc, "color": "mint"},
                })
                if modalidad in ("voz", "ambos"):
                    await websocket.send_json({"type": "voz", "frases": [desc]})
                await websocket.send_json({"type": "answer", "text": desc, "route": "centinela", "model": "sentinela_vision"})
                continue

            texto = (msg.get("text") or "").strip()
            if not texto:
                continue

            async def on_event(ev) -> None:
                await websocket.send_json({"type": "trace", **ev.to_dict()})

            conductor = _make_conductor(on_event=on_event)
            answer = await conductor.attend(texto)
            run = conductor.last_run

            # Payload de presentación (proceso + resultado dinámico + modalidad).
            await websocket.send_json(construir_presentacion(run, modalidad))
            # Frases para TTS streaming (el cliente pide /tts por frase). Solo si hay voz.
            if modalidad in ("voz", "ambos"):
                voz = construir_presentacion(run, modalidad).get("voz", "")
                await websocket.send_json({"type": "voz", "frases": frases(voz)})
            # Compat con la página mínima.
            await websocket.send_json(
                {"type": "answer", "text": answer, "route": run["route"], "model": run["model"]}
            )
    except WebSocketDisconnect:
        return


@app.get("/tts")
async def tts(text: str = Query(..., max_length=2000)):
    """Audio TTS (WAV) de una frase. 204 si no hay voz disponible (cliente degrada)."""
    voz = await _get_tts()
    if voz is None:
        return Response(status_code=204)
    wav = voz.sintetizar_wav(text)
    if not wav:
        return Response(status_code=204)
    return Response(content=wav, media_type="audio/wav")


@app.get("/lite", response_class=HTMLResponse)
async def lite() -> str:
    """Página mínima (sin dependencias) — respaldo si el frontend no está compilado."""
    return INDEX_HTML


INDEX_HTML = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NOVA</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; font-family:-apple-system,system-ui,sans-serif; background:#0b0d12; color:#e8eaf0; }
  header { padding:14px 18px; font-weight:700; letter-spacing:.5px; border-bottom:1px solid #1d2230; }
  #wrap { max-width:760px; margin:0 auto; padding:16px; }
  #log { min-height:40vh; }
  .msg { margin:10px 0; }
  .you { color:#8ab4ff; }
  .nova { color:#e8eaf0; white-space:pre-wrap; }
  .trace { color:#5b667a; font-size:12px; margin:2px 0; }
  .trace .alerta, .trace.alerta { color:#e0a83a; }
  form { display:flex; gap:8px; position:sticky; bottom:0; background:#0b0d12; padding:12px 0; }
  input { flex:1; padding:12px; border-radius:10px; border:1px solid #283044; background:#11151f; color:#e8eaf0; font-size:16px; }
  button { padding:12px 16px; border:0; border-radius:10px; background:#3a6df0; color:#fff; font-weight:600; }
  #status { font-size:12px; color:#5b667a; }
</style>
</head>
<body>
<header>NOVA <span id="status">conectando…</span></header>
<div id="wrap">
  <div id="log"></div>
  <form id="f"><input id="i" autocomplete="off" placeholder="Hablale a NOVA…" autofocus><button>Enviar</button></form>
</div>
<script>
const log = document.getElementById('log');
const status = document.getElementById('status');
function add(cls, txt){ const d=document.createElement('div'); d.className=cls; d.textContent=txt; log.appendChild(d); window.scrollTo(0,document.body.scrollHeight); return d; }
let ws, ready=false;
function connect(){
  ws = new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/ws');
  ws.onopen = ()=>{ ready=true; status.textContent='● en línea'; };
  ws.onclose = ()=>{ ready=false; status.textContent='○ desconectado — reintentando'; setTimeout(connect,1500); };
  ws.onmessage = (e)=>{ const m=JSON.parse(e.data);
    if(m.type==='trace'){ const t=add('trace msg','· '+m.etapa+'/'+m.agente+(m.modelo&&m.modelo!=='-'?' ['+m.modelo+']':'')+': '+m.detalle); if(m.estado==='alerta')t.classList.add('alerta'); }
    else if(m.type==='answer'){ add('msg nova','NOVA> '+m.text); }
  };
}
connect();
document.getElementById('f').addEventListener('submit',(e)=>{
  e.preventDefault(); const i=document.getElementById('i'); const t=i.value.trim(); if(!t||!ready)return;
  add('msg you','tú> '+t); ws.send(t); i.value='';
});
</script>
</body>
</html>"""


# --- Frontend compilado (Three.js: esfera + cámara + config) -------------------
# Servido en `/` desde frontend/dist. Si no está compilado (`npm run build`), `/`
# cae a la página mínima. Se monta AL FINAL para que las rutas API tengan prioridad.
_DIST = Path(os.environ.get("NOVA_FRONTEND_DIST", str(PROJECT_ROOT / "frontend" / "dist")))
if (_DIST / "index.html").is_file():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
else:  # sin build → la raíz sirve la página mínima
    @app.get("/", response_class=HTMLResponse)
    async def _index_fallback() -> str:
        return INDEX_HTML


def main() -> int:
    """Arranca el servidor (uvicorn). Host/puerto por entorno.

    En el contenedor escucha en 0.0.0.0; la restricción a la LAN se hace en el
    `ports:` del compose (atado a la IP LAN, nunca a una interfaz pública).
    """
    import uvicorn  # lazy: importar app no requiere uvicorn (tests)

    host = os.environ.get("NOVA_HOST", "0.0.0.0")
    port = int(os.environ.get("NOVA_PORT", "8000"))
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
