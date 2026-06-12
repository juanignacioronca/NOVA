// NOVA — frontend: esfera audio-reactiva + voz (STT navegador) + cámara local +
// modo configuración + flujo en vivo + pantalla dinámica. Se conecta por WS /ws.
import "./style.css";
import { AudioEngine } from "./audio";
import { CameraView } from "./camera";
import { ConfigView } from "./config/config";
import { FlowView } from "./flow/flow";
import { ModalityControls } from "./modality";
import { Supernova } from "./nova/supernova";
import { Screen } from "./screen/screen";
import type { Modalidad, Presentacion, ServerMsg, TraceEvent, VozMsg } from "./types";
import { VoiceInput } from "./voice";
import { NovaSocket } from "./ws";

const app = document.getElementById("app") as HTMLElement;

function div(cls?: string): HTMLElement {
  const d = document.createElement("div");
  if (cls) d.className = cls;
  return d;
}
function btn(cls: string, txt: string): HTMLButtonElement {
  const b = document.createElement("button");
  b.className = cls;
  b.textContent = txt;
  b.type = "button";
  return b;
}

// --- Header: marca + estado + controles ---
const hdr = div("hdr");
hdr.innerHTML =
  `<div class="brand">NOVA</div>` +
  `<div class="status"><span class="dot" id="dot"></span><span id="statustxt">conectando…</span></div>` +
  `<div class="spacer"></div>`;
const ctrls = div("ctrls");
const btnMic = btn("ico", "🎙");
btnMic.title = "Hablarle a NOVA (voz)";
const btnCam = btn("ico", "📷");
btnCam.title = "Cámara (local)";
const btnCfg = btn("ico", "⚙");
btnCfg.title = "Configuración";
const toggle = document.createElement("label");
toggle.className = "toggle";
const chk = document.createElement("input");
chk.type = "checkbox";
toggle.append(chk, document.createTextNode(" flujo"));
ctrls.append(btnMic, btnCam, btnCfg, toggle);
hdr.append(ctrls);

// --- Stage: NOVA + panel (+ cámara flotante + overlay config) ---
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

const camera = new CameraView();
const config = new ConfigView();
stage.append(novaWrap, panel, camera.el, config.el);

// --- Footer: modalidad + composer ---
const foot = div("foot");
const composer = document.createElement("form");
composer.className = "composer";
const input = document.createElement("input");
input.placeholder = "Hablale o escribile a NOVA…";
input.autocomplete = "off";
const send = btn("send", "▶");
send.classList.remove("ico");
composer.append(input, send);

const audio = new AudioEngine();
const voice = new VoiceInput();
let modalidadActual: Modalidad = "ambos";
let escuchando = false;
const modality = new ModalityControls((m) => {
  socket.enviarModalidad(m);
  aplicarModalidad(m);
});
foot.append(modality.el, composer);

app.append(hdr, stage, foot);

// --- NOVA audio-reactiva (TTS + micrófono mientras escucha) ---
const nova = new Supernova(novaWrap);
function loop() {
  const base = audio.nivel();
  const mic = escuchando ? audio.micNivel() * 1.5 : 0;
  nova.setNivel(Math.max(base, mic));
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

// --- Botón cámara (modo centinela: vigila siempre, avisa en cambios) ---
camera.onCambio = (foto) => {
  socket.enviarFrame(foto); // algo cambió → que NOVA mire
};
camera.onEstado = (vigilando, nivel) => {
  novaLabel.textContent = vigilando ? (nivel > 0.06 ? "centinela ●" : "centinela") : "núcleo";
};
btnCam.onclick = async () => {
  const on = await camera.toggle();
  btnCam.classList.toggle("active", on);
  if (!on) novaLabel.textContent = "núcleo";
};

// --- Botón configuración ---
let cfgAbierta = false;
btnCfg.onclick = async () => {
  cfgAbierta = !cfgAbierta;
  btnCfg.classList.toggle("active", cfgAbierta);
  if (cfgAbierta) await config.abrir();
  else config.cerrar();
};

// --- Voz: manos libres (loop continuo con Web Speech) ---
if (!voice.disponible()) {
  btnMic.disabled = true;
  btnMic.title = "Tu navegador no soporta dictado por voz (probá Chrome/Edge)";
}
voice.onState = (on) => {
  escuchando = on;
  btnMic.classList.toggle("active", voice.continuo);
};
voice.onInterim = (t) => {
  input.value = t;
};
voice.onFinal = (t) => {
  input.value = t;
  enviar();
};
btnMic.onclick = () => {
  audio.resume();
  audio.habilitarMic(); // para que la esfera reaccione a tu voz
  voice.toggle(); // enciende/apaga el loop de escucha permanente
  btnMic.classList.toggle("active", voice.continuo);
};

// Mientras NOVA habla, pausar la escucha (no transcribir su propia voz).
audio.onHablarInicio = () => voice.pausar();
audio.onHablarFin = () => voice.reanudar();

// --- Estado de conexión + mensajes ---
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

audio.onBargeIn = () => socket.enviarStop();

// --- Envío (texto o voz) ---
let micPedido = false;
function enviar() {
  const t = input.value.trim();
  if (!t) return;
  audio.resume();
  if (!micPedido) {
    micPedido = true;
    audio.habilitarMic();
  }
  flow.reset();
  socket.enviarTexto(t);
  input.value = "";
}
composer.onsubmit = (e) => {
  e.preventDefault();
  enviar();
};
