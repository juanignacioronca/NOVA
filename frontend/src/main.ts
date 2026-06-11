// NOVA — frontend: NOVA audio-reactiva + flujo en vivo + pantalla dinámica +
// botones de modalidad. Se conecta al backend por WS /ws y reproduce el TTS por /tts.
import "./style.css";
import { AudioEngine } from "./audio";
import { FlowView } from "./flow/flow";
import { ModalityControls } from "./modality";
import { Supernova } from "./nova/supernova";
import { Screen } from "./screen/screen";
import type { Modalidad, Presentacion, ServerMsg, TraceEvent, VozMsg } from "./types";
import { NovaSocket } from "./ws";

const app = document.getElementById("app") as HTMLElement;

// --- Header ---
const hdr = div("hdr");
hdr.innerHTML =
  `<div class="brand">NOVA</div>` +
  `<div class="status"><span class="dot" id="dot"></span><span id="statustxt">conectando…</span></div>` +
  `<div class="spacer"></div>`;
const toggle = document.createElement("label");
toggle.className = "toggle";
const chk = document.createElement("input");
chk.type = "checkbox";
toggle.append(chk, document.createTextNode(" flujo en vivo"));
hdr.appendChild(toggle);

// --- Stage: NOVA + panel ---
const stage = div("stage");
const novaWrap = div();
novaWrap.id = "nova";
const novaLabel = div("nova-label");
novaLabel.textContent = "núcleo";
novaWrap.appendChild(novaLabel);

const panel = div("panel");
const screen = new Screen();
const flow = new FlowView();
flow.el.hidden = true;
panel.append(screen.el, flow.el);
stage.append(novaWrap, panel);

// --- Footer: modalidad + composer ---
const foot = div("foot");
const composer = document.createElement("form");
composer.className = "composer";
const input = document.createElement("input");
input.placeholder = "Hablale a NOVA…";
input.autocomplete = "off";
const send = document.createElement("button");
send.type = "submit";
send.textContent = "▶";
composer.append(input, send);

const audio = new AudioEngine();
let modalidadActual: Modalidad = "ambos";
const modality = new ModalityControls((m) => {
  socket.enviarModalidad(m);
  aplicarModalidad(m);
});
foot.append(modality.el, composer);

app.append(hdr, stage, foot);

// --- NOVA audio-reactiva ---
const nova = new Supernova(novaWrap);
function loop() {
  nova.setNivel(audio.nivel());
  requestAnimationFrame(loop);
}
loop();

function aplicarModalidad(m: Modalidad) {
  modalidadActual = m;
  stage.classList.remove("solo-voz", "solo-pantalla");
  if (m === "voz") stage.classList.add("solo-voz");
  if (m === "pantalla") stage.classList.add("solo-pantalla");
}

// --- Flujo en vivo (toggle) ---
chk.onchange = () => {
  flow.el.hidden = !chk.checked;
  screen.el.hidden = chk.checked;
};

// --- Estado de conexión ---
const dot = document.getElementById("dot") as HTMLElement;
const stxt = document.getElementById("statustxt") as HTMLElement;

const socket = new NovaSocket(onMsg, (online) => {
  dot.classList.toggle("on", online);
  stxt.textContent = online ? "● en línea" : "○ desconectado";
});

function onMsg(msg: ServerMsg) {
  if (msg.type === "trace") {
    flow.onTrace(msg as TraceEvent);
  } else if (msg.type === "presentacion") {
    screen.render(msg as Presentacion);
  } else if (msg.type === "voz") {
    if (modalidadActual !== "pantalla") audio.hablar((msg as VozMsg).frases);
  }
}

// Barge-in: si el usuario habla mientras NOVA habla, cortar + avisar al backend.
audio.onBargeIn = () => socket.enviarStop();

let micPedido = false;
composer.onsubmit = (e) => {
  e.preventDefault();
  const t = input.value.trim();
  if (!t) return;
  audio.resume(); // desbloquea el AudioContext (autoplay policy)
  if (!micPedido) {
    micPedido = true;
    audio.habilitarMic();
  }
  flow.reset();
  socket.enviarTexto(t);
  input.value = "";
};

function div(cls?: string): HTMLElement {
  const d = document.createElement("div");
  if (cls) d.className = cls;
  return d;
}
