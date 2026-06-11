// Vista de flujo en vivo: replica el layout del simulador (Percepción → Conductor
// → Local | Empresa → Salidas; + Memoria/Herramientas/Auditoría) pero data-driven
// desde los TraceEvent reales: cada nodo se enciende cuando su agente actúa.
import type { TraceEvent } from "../types";

interface NodeDef { id: string; label: string; grupo: string; }
interface LaneDef { titulo: string; nodos: NodeDef[]; }

const LANES: LaneDef[] = [
  { titulo: "Percepción", nodos: [
    { id: "percepcion", label: "Audio · Texto · Video", grupo: "local" },
    { id: "memoria", label: "Memoria", grupo: "memoria" },
    { id: "herramientas", label: "Herramientas", grupo: "" },
  ]},
  { titulo: "Conductor", nodos: [
    { id: "conductor", label: "Comprensión + Orquestación", grupo: "" },
  ]},
  { titulo: "Equipos", nodos: [
    { id: "respuestas_rapidas", label: "Respuestas rápidas", grupo: "local" },
    { id: "sentinela", label: "Sentinela / Visión", grupo: "local" },
    { id: "empresa", label: "PMO (Empresa)", grupo: "nube" },
    { id: "estrategia", label: "Estrategia", grupo: "nube" },
    { id: "finanzas", label: "Finanzas", grupo: "nube" },
  ]},
  { titulo: "Salidas", nodos: [
    { id: "salida", label: "Voz + Pantalla", grupo: "local" },
    { id: "auditoria", label: "Auditoría (async)", grupo: "" },
  ]},
];

export class FlowView {
  el: HTMLElement;
  private nodes = new Map<string, HTMLElement>();
  private equiposLane!: HTMLElement;
  private log: HTMLElement;
  private timers = new Map<string, number>();

  constructor() {
    this.el = document.createElement("div");
    const grid = document.createElement("div");
    grid.className = "flow";
    for (const lane of LANES) {
      const col = document.createElement("div");
      col.className = "lane";
      const h = document.createElement("h4");
      h.textContent = lane.titulo;
      col.appendChild(h);
      for (const n of lane.nodos) col.appendChild(this.crearNodo(n));
      if (lane.titulo === "Equipos") this.equiposLane = col;
      grid.appendChild(col);
    }
    this.log = document.createElement("div");
    this.log.className = "tracelog";
    this.el.appendChild(grid);
    this.el.appendChild(this.log);
  }

  private crearNodo(n: NodeDef): HTMLElement {
    const d = document.createElement("div");
    d.className = "node" + (n.grupo ? " " + n.grupo : "");
    d.innerHTML = `<div>${n.label}</div><div class="k">${n.id}</div>`;
    this.nodes.set(n.id, d);
    return d;
  }

  private resolver(ev: TraceEvent): string {
    const a = ev.agente || "";
    const e = ev.etapa || "";
    if (e === "percepcion" || ["audio", "video", "texto"].includes(a)) return "percepcion";
    if (e === "memoria" || a === "memoria_contexto") return "memoria";
    if (e === "salida" || e === "proactivo" || ["voz", "pantalla"].includes(a)) return "salida";
    if (a === "respuestas_rapidas") return "respuestas_rapidas";
    if (a === "sentinela" || a === "conductor_vision") return "sentinela";
    if (a === "empresa" || a.startsWith("pmo")) return "empresa";
    if (a.startsWith("estrategia")) return "estrategia";
    if (a.startsWith("finanzas")) return "finanzas";
    if (a.endsWith("_lider")) return a.replace("_lider", ""); // área dinámica
    return "conductor";
  }

  onTrace(ev: TraceEvent) {
    const id = this.resolver(ev);
    let node = this.nodes.get(id);
    if (!node && this.equiposLane) {
      node = this.crearNodo({ id, label: id, grupo: ev.grupo || "nube" });
      this.equiposLane.appendChild(node);
    }
    if (node) this.encender(node, id, ev.estado);

    const linea = document.createElement("div");
    linea.textContent = `${markEstado(ev.estado)} ${ev.etapa}/${ev.agente}${ev.modelo && ev.modelo !== "-" ? " [" + ev.modelo + "]" : ""}: ${ev.detalle}`;
    if (ev.estado === "alerta") linea.className = "alerta";
    this.log.appendChild(linea);
    this.log.scrollTop = this.log.scrollHeight;
  }

  private encender(node: HTMLElement, id: string, estado: string) {
    node.classList.add("on");
    if (estado === "alerta") node.classList.add("alerta");
    const prev = this.timers.get(id);
    if (prev) clearTimeout(prev);
    this.timers.set(id, window.setTimeout(() => {
      node.classList.remove("on", "alerta");
    }, 1400));
  }

  reset() {
    this.log.innerHTML = "";
    for (const n of this.nodes.values()) n.classList.remove("on", "alerta");
  }
}

function markEstado(estado: string): string {
  return estado === "alerta" ? "⚠" : estado === "pregunta" ? "?" : "·";
}
