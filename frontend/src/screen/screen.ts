// Pantalla con contenido dinámico: renderiza el `resultado` estructurado que
// manda el backend (tarjeta / itinerario / tabla / pregunta / texto) + meta.
import type { Presentacion, Resultado } from "../types";

export class Screen {
  el: HTMLElement;

  constructor() {
    this.el = document.createElement("div");
    this.vacio();
  }

  private vacio() {
    this.el.innerHTML = `<div class="card"><span class="tick tl"></span><span class="tick br"></span>
      <h3>NOVA</h3><div class="muted">Hablale o escribile. Las respuestas aparecen acá.</div></div>`;
  }

  render(p: Presentacion) {
    this.el.innerHTML = "";
    this.el.appendChild(this.tarjetaResultado(p.resultado));
    if (p.meta) this.el.appendChild(this.meta(p));
  }

  private tarjetaResultado(r: Resultado): HTMLElement {
    const card = document.createElement("div");
    card.className = "card" + (r.color ? " " + r.color : "");
    card.innerHTML = `<span class="tick tl"></span><span class="tick br"></span><h3>${esc(r.titulo)}</h3>`;
    const body = document.createElement("div");

    if (r.tipo === "itinerario" && r.pasos) {
      for (const p of r.pasos) {
        const step = document.createElement("div");
        step.className = "step";
        const badges =
          `<span class="badge area">${esc(p.area)}</span>` +
          (p.estrategia ? `<span class="badge est">estrategia</span>` : "") +
          (p.finanzas ? `<span class="badge fin">finanzas</span>` : "");
        step.innerHTML = `<div class="n">${p.n}</div><div>${esc(p.descripcion)} ${badges}</div>`;
        body.appendChild(step);
      }
    } else if (r.tipo === "pregunta") {
      body.className = "pre";
      body.textContent = r.texto || "";
    } else if (r.tipo === "tarjeta") {
      body.className = "pre";
      body.textContent = r.cuerpo || "";
    } else {
      body.className = "pre";
      body.textContent = r.texto || "";
    }
    card.appendChild(body);
    return card;
  }

  private meta(p: Presentacion): HTMLElement {
    const c = document.createElement("div");
    c.className = "card";
    const mem = (p.meta.memoria || []).map((m) => `<span class="badge mem">${esc(m)}</span>`).join(" ");
    c.innerHTML = `<h3>Proceso</h3>
      <div class="muted">ruta: ${esc(p.meta.route || "-")} · intención: ${esc(p.meta.intent || "-")} · modelo: ${esc(p.meta.model || "-")}</div>
      ${mem ? `<div style="margin-top:6px">memoria: ${mem}</div>` : ""}
      <div class="tracelog" style="margin-top:8px">${(p.proceso || [])
        .map((e) => `<div${e.estado === "alerta" ? ' class="alerta"' : ""}>· ${esc(e.etapa)}/${esc(e.agente)}: ${esc(e.detalle)}</div>`)
        .join("")}</div>`;
    return c;
  }
}

function esc(s: string): string {
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c] as string));
}
