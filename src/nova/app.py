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

import os
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from . import __version__
from .core.conductor import Conductor
from .core.trace import EventCallback
from .core.world_state import WorldState
from .env import load_env
from .logging.registro import Registro

load_env()  # claves desde .env si existe (en Docker llegan por env_file)

app = FastAPI(title="NOVA", version=__version__)

# Estado compartido del servicio (un solo mundo; conductores por request).
_world = WorldState()
_registro = Registro()


def _make_conductor(on_event: Optional[EventCallback] = None) -> Conductor:
    return Conductor(world=_world, registro=_registro, on_event=on_event)


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


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            texto = (await websocket.receive_text()).strip()
            if not texto:
                continue

            async def on_event(ev) -> None:
                await websocket.send_json({"type": "trace", **ev.to_dict()})

            conductor = _make_conductor(on_event=on_event)
            answer = await conductor.attend(texto)
            run = conductor.last_run
            await websocket.send_json(
                {"type": "answer", "text": answer, "route": run["route"], "model": run["model"]}
            )
    except WebSocketDisconnect:
        return


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
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
