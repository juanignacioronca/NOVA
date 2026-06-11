// Botones de modalidad: Solo voz / Solo pantalla / Ambos (manual).
import type { Modalidad } from "./types";

const OPCIONES: Array<{ id: Modalidad; label: string }> = [
  { id: "voz", label: "Solo voz" },
  { id: "pantalla", label: "Solo pantalla" },
  { id: "ambos", label: "Ambos" },
];

export class ModalityControls {
  el: HTMLElement;
  actual: Modalidad = "ambos";
  private onChange: (m: Modalidad) => void;

  constructor(onChange: (m: Modalidad) => void) {
    this.onChange = onChange;
    this.el = document.createElement("div");
    this.el.className = "modality";
    for (const opt of OPCIONES) {
      const b = document.createElement("button");
      b.className = "mbtn" + (opt.id === this.actual ? " active" : "");
      b.textContent = opt.label;
      b.dataset.id = opt.id;
      b.onclick = () => this.set(opt.id);
      this.el.appendChild(b);
    }
  }

  set(m: Modalidad) {
    this.actual = m;
    for (const b of Array.from(this.el.querySelectorAll<HTMLButtonElement>(".mbtn"))) {
      b.classList.toggle("active", b.dataset.id === m);
    }
    this.onChange(m);
  }
}
