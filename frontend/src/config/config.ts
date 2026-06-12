// Modo configuración: editor del roster de NOVA contra /api/config/*.
//  - "Agentes": por equipo, cada sub-agente con su PROMPT (rol), su modelo,
//    sus herramientas y a quién puede consultar. Crear / borrar agentes.
//  - "Núcleo": el mapa agente→modelo de models.yaml (conductor, PMO, áreas…)
//    con desplegables — cambiar el modelo de cualquier pieza sin tocar código.
//  - "Prompts": los prompts del sistema (personalidad, clasificador, planificador…)
//    editables en caliente, con vuelta al default de fábrica.
//  - "Estado": chequeo en vivo de proveedores (Ollama/Gemini/Groq/…): qué responde,
//    qué falta, latencia y modelos pulled. Para diagnosticar "por qué responde raro".
//  - "Pendientes": lo que NOVA anotó que no puede hacer / datos que le faltan.
//  - "YAML crudo": el texto completo de teams/models/tools/prompts (power-user).
// Todo se guarda en los .yaml del backend (con backup) y recarga en caliente.

interface SubAgente {
  name: string;
  rol: string;
  model_key: string;
  model_spec: string;
  model_compartido: number;
  tools: string[];
  puede_consultar: string[];
}
interface Equipo {
  id: string;
  tipo: string;
  lider?: string;
  sub_agentes: SubAgente[];
}
interface CoreAgent {
  key: string;
  spec: string;
  cadena: string[];
  descripcion: string;
}
interface PromptItem {
  name: string;
  titulo: string;
  descripcion: string;
  texto: string;
  es_default: boolean;
}
interface ProveedorEstado {
  name: string;
  ok: boolean;
  state: string;
  detail: string;
}

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  cls?: string,
  txt?: string,
): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (txt) e.textContent = txt;
  return e;
}

async function api(method: string, url: string, body?: unknown) {
  const r = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}

export class ConfigView {
  el: HTMLElement;
  private body: HTMLElement;
  private toast: HTMLElement;
  private modelos: string[] = [];
  private allTools: string[] = [];

  constructor() {
    this.el = el("div", "config");
    this.el.hidden = true;
    const head = el("div", "config-head");
    head.append(el("h2", undefined, "Configuración de NOVA"));
    const tabs = el("div", "config-tabs");
    const defs: Array<[string, () => Promise<void>]> = [
      ["Agentes", () => this.renderAgentes()],
      ["Núcleo", () => this.renderNucleo()],
      ["Prompts", () => this.renderPrompts()],
      ["Estado", () => this.renderEstado()],
      ["Pendientes", () => this.renderPendientes()],
      ["YAML crudo", () => this.renderRaw()],
    ];
    const botones: HTMLButtonElement[] = [];
    for (const [titulo, render] of defs) {
      const b = el("button", "ctab", titulo);
      b.onclick = () => {
        for (const x of botones) x.classList.toggle("active", x === b);
        void render();
      };
      botones.push(b);
      tabs.append(b);
    }
    botones[0].classList.add("active");
    head.append(tabs);
    this.toast = el("div", "config-toast");
    this.body = el("div", "config-body");
    this.el.append(head, this.toast, this.body);
  }

  private aviso(txt: string, ok = true) {
    this.toast.textContent = txt;
    this.toast.classList.toggle("err", !ok);
    this.toast.classList.add("show");
    setTimeout(() => this.toast.classList.remove("show"), 2600);
  }

  private cargando() {
    this.body.replaceChildren(el("div", "muted", "Cargando…"));
  }

  private error(e: unknown) {
    this.body.replaceChildren(el("div", "config-toast err show", "Error: " + (e as Error).message));
  }

  async abrir() {
    this.el.hidden = false;
    await this.renderAgentes();
  }
  cerrar() {
    this.el.hidden = true;
  }

  private async cargarModelos(): Promise<string[]> {
    if (!this.modelos.length) {
      const mods = await api("GET", "/api/config/models");
      this.modelos = mods.models || [];
    }
    return this.modelos;
  }

  private modeloSelect(actual: string): HTMLSelectElement {
    const sel = el("select", "field");
    const opciones = this.modelos.includes(actual) ? this.modelos : [actual, ...this.modelos];
    for (const m of opciones) {
      const o = el("option", undefined, m);
      o.value = m;
      if (m === actual) o.selected = true;
      sel.append(o);
    }
    return sel;
  }

  // --- Pestaña Agentes ---
  private async renderAgentes() {
    this.cargando();
    try {
      this.modelos = [];
      const [ag] = await Promise.all([api("GET", "/api/config/agents"), this.cargarModelos()]);
      this.allTools = ag.all_tools || [];
      this.body.replaceChildren();
      for (const eq of ag.teams as Equipo[]) this.body.append(this.equipoCard(eq));
    } catch (e) {
      this.error(e);
    }
  }

  private equipoCard(eq: Equipo): HTMLElement {
    const wrap = el("div", "team");
    const h = el("div", "team-h");
    h.append(el("span", "team-name", eq.id), el("span", "badge", eq.tipo));
    const addBtn = el("button", "btn ghost", "+ agente");
    addBtn.onclick = () => this.nuevoAgente(eq.id, agentsBox);
    h.append(addBtn);
    const agentsBox = el("div", "agents");
    for (const sa of eq.sub_agentes) agentsBox.append(this.agenteCard(eq.id, sa));
    wrap.append(h, agentsBox);
    return wrap;
  }

  private agenteCard(team: string, sa: SubAgente): HTMLElement {
    const c = el("div", "agent");
    const top = el("div", "agent-top");
    top.append(el("span", "agent-name", sa.name));
    if (sa.model_compartido > 1)
      top.append(el("span", "badge warn", `modelo compartido ×${sa.model_compartido}`));
    c.append(top);

    c.append(el("label", "flabel", "Prompt (rol)"));
    const rol = el("textarea", "field");
    rol.value = sa.rol;
    rol.rows = 2;
    c.append(rol);

    const row = el("div", "frow");
    const colM = el("div", "fcol");
    colM.append(el("label", "flabel", "Modelo"));
    const modelo = this.modeloSelect(sa.model_spec);
    colM.append(modelo);
    const colT = el("div", "fcol");
    colT.append(el("label", "flabel", `Herramientas (${this.allTools.join(", ") || "—"})`));
    const tools = el("input", "field") as HTMLInputElement;
    tools.value = sa.tools.join(", ");
    colT.append(tools);
    row.append(colM, colT);
    c.append(row);

    c.append(el("label", "flabel", "Puede consultar (otros agentes)"));
    const consultar = el("input", "field") as HTMLInputElement;
    consultar.value = sa.puede_consultar.join(", ");
    c.append(consultar);

    const acc = el("div", "agent-actions");
    const save = el("button", "btn", "Guardar");
    const del = el("button", "btn danger", "Borrar");
    acc.append(save, del);
    c.append(acc);

    const lista = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

    save.onclick = async () => {
      save.disabled = true;
      try {
        const r = await api("PUT", `/api/config/agents/${team}/${sa.name}`, {
          rol: rol.value,
          model_spec: modelo.value,
          tools: lista(tools.value),
          puede_consultar: lista(consultar.value),
        });
        this.aviso(r.aviso || `${sa.name} guardado ✓`);
      } catch (e) {
        this.aviso((e as Error).message, false);
      }
      save.disabled = false;
    };
    del.onclick = async () => {
      if (!confirm(`¿Borrar el agente "${sa.name}"?`)) return;
      try {
        await api("DELETE", `/api/config/agents/${team}/${sa.name}`);
        c.remove();
        this.aviso(`${sa.name} borrado`);
      } catch (e) {
        this.aviso((e as Error).message, false);
      }
    };
    return c;
  }

  private async nuevoAgente(team: string, box: HTMLElement) {
    const name = prompt("Nombre del nuevo agente (sin espacios):")?.trim();
    if (!name) return;
    try {
      await api("POST", `/api/config/agents/${team}`, {
        name,
        rol: "Describí qué hace este agente.",
        model_spec: this.modelos[0] || "ollama:qwen2.5:7b",
        tools: [],
        puede_consultar: [],
      });
      box.append(
        this.agenteCard(team, {
          name,
          rol: "Describí qué hace este agente.",
          model_key: name,
          model_spec: this.modelos[0] || "ollama:qwen2.5:7b",
          model_compartido: 1,
          tools: [],
          puede_consultar: [],
        }),
      );
      this.aviso(`${name} creado ✓`);
    } catch (e) {
      this.aviso((e as Error).message, false);
    }
  }

  // --- Pestaña Núcleo: mapa agente→modelo de models.yaml ---
  private async renderNucleo() {
    this.cargando();
    try {
      this.modelos = [];
      const [core] = await Promise.all([api("GET", "/api/config/core"), this.cargarModelos()]);
      this.body.replaceChildren();
      this.body.append(
        el(
          "div",
          "muted",
          "Qué modelo usa cada pieza del núcleo (models.yaml). Los cambios aplican al próximo mensaje, sin reiniciar. Regla: lo que corre siempre → local (ollama); lo complejo → nube free-tier.",
        ),
      );
      const box = el("div", "agents");
      for (const a of core.agents as CoreAgent[]) box.append(this.coreCard(a));
      box.append(
        this.coreCard({
          key: "_fallback",
          spec: core.fallback,
          cadena: [core.fallback],
          descripcion: "Respaldo global ante 429/caída de cualquier proveedor",
        }),
      );
      this.body.append(box);
    } catch (e) {
      this.error(e);
    }
  }

  private coreCard(a: CoreAgent): HTMLElement {
    const c = el("div", "agent");
    const top = el("div", "agent-top");
    top.append(el("span", "agent-name", a.key === "_fallback" ? "fallback global" : a.key));
    if (a.cadena.length > 1)
      top.append(el("span", "badge", `+${a.cadena.length - 1} fallback`));
    c.append(top);
    if (a.descripcion) c.append(el("div", "muted", a.descripcion));
    const sel = this.modeloSelect(a.spec);
    c.append(sel);
    if (a.cadena.length > 1)
      c.append(el("div", "muted", "cadena: " + a.cadena.join(" → ")));
    const acc = el("div", "agent-actions");
    const save = el("button", "btn", "Guardar");
    acc.append(save);
    c.append(acc);
    save.onclick = async () => {
      save.disabled = true;
      try {
        await api("PUT", `/api/config/core/${a.key}`, { spec: sel.value });
        this.aviso(`${a.key} → ${sel.value} ✓`);
      } catch (e) {
        this.aviso((e as Error).message, false);
      }
      save.disabled = false;
    };
    return c;
  }

  // --- Pestaña Prompts: los textos del sistema, editables ---
  private async renderPrompts() {
    this.cargando();
    try {
      const r = await api("GET", "/api/config/prompts");
      this.body.replaceChildren();
      this.body.append(
        el(
          "div",
          "muted",
          "La personalidad y las instrucciones internas de NOVA. Editá, guardá y probá en el chat: aplica al próximo mensaje. «Restaurar» vuelve al default de fábrica.",
        ),
      );
      for (const p of r.prompts as PromptItem[]) this.body.append(this.promptCard(p));
    } catch (e) {
      this.error(e);
    }
  }

  private promptCard(p: PromptItem): HTMLElement {
    const c = el("div", "agent prompt-card");
    const top = el("div", "agent-top");
    top.append(el("span", "agent-name", p.titulo));
    const estado = el("span", "badge" + (p.es_default ? "" : " warn"), p.es_default ? "default" : "personalizado");
    top.append(estado);
    c.append(top);
    c.append(el("div", "muted", p.descripcion));
    const ta = el("textarea", "field");
    ta.value = p.texto;
    ta.rows = 7;
    ta.spellcheck = false;
    c.append(ta);
    const acc = el("div", "agent-actions");
    const save = el("button", "btn", "Guardar");
    const reset = el("button", "btn ghost", "Restaurar default");
    acc.append(save, reset);
    c.append(acc);

    const guardar = async (texto: string) => {
      const r = await api("PUT", `/api/config/prompts/${p.name}`, { text: texto });
      estado.textContent = r.es_default ? "default" : "personalizado";
      estado.className = "badge" + (r.es_default ? "" : " warn");
    };
    save.onclick = async () => {
      save.disabled = true;
      try {
        await guardar(ta.value);
        this.aviso(`«${p.titulo}» guardado ✓`);
      } catch (e) {
        this.aviso((e as Error).message, false);
      }
      save.disabled = false;
    };
    reset.onclick = async () => {
      try {
        await guardar("");
        const r = await api("GET", "/api/config/prompts");
        const fresco = (r.prompts as PromptItem[]).find((x) => x.name === p.name);
        if (fresco) ta.value = fresco.texto;
        this.aviso(`«${p.titulo}» restaurado al default`);
      } catch (e) {
        this.aviso((e as Error).message, false);
      }
    };
    return c;
  }

  // --- Pestaña Estado: doctor de proveedores en vivo ---
  private async renderEstado() {
    this.cargando();
    try {
      const r = await api("GET", "/api/config/estado");
      this.body.replaceChildren();
      const bar = el("div", "raw-bar");
      bar.append(
        el(
          "div",
          "muted",
          "Quién está respondiendo de verdad. Si Ollama no responde o falta una clave, NOVA degrada a stub (respuestas de prueba).",
        ),
      );
      const refresh = el("button", "btn", "Re-chequear");
      refresh.onclick = () => this.renderEstado();
      bar.append(refresh);
      this.body.append(bar);

      const box = el("div", "agents");
      for (const p of r.proveedores as ProveedorEstado[]) {
        const c = el("div", "agent");
        const top = el("div", "agent-top");
        const marca = p.ok ? "✓" : p.state === "error" ? "✗" : "•";
        const m = el("span", "agent-name", `${marca} ${p.name}`);
        m.style.color = p.ok ? "var(--mint)" : p.state === "error" ? "#ff7a7a" : "var(--amber)";
        top.append(m, el("span", "badge", p.state));
        c.append(top);
        c.append(el("div", "muted", p.detail || ""));
        box.append(c);
      }
      this.body.append(box);

      const tags = (r.ollama_models || []) as string[];
      const om = el("div", "team");
      om.append(el("div", "team-name", "Modelos pulled en Ollama"));
      om.append(
        el(
          "div",
          "muted",
          tags.length
            ? tags.join(" · ")
            : "Ninguno (¿`ollama serve` corriendo? ¿`ollama pull llama3.2:3b`?). Sin esto, lo local cae a stub.",
        ),
      );
      this.body.append(om);
    } catch (e) {
      this.error(e);
    }
  }

  // --- Pestaña Pendientes (lo que NOVA no pudo hacer / datos que le faltan) ---
  private async renderPendientes() {
    this.cargando();
    try {
      const r = await api("GET", "/api/config/pendientes");
      const items = (r.pendientes || []) as Array<{ descripcion: string; contexto?: string; tipo?: string }>;
      this.body.replaceChildren();
      const intro = el(
        "div",
        "muted",
        "Acá NOVA anota lo que todavía no puede hacer o los datos que le faltan (ej. dónde vivís). Sirve para decidir qué herramientas o datos sumar.",
      );
      this.body.append(intro);
      if (!items.length) {
        this.body.append(el("div", "team", "Sin pendientes anotados. 🎉"));
        return;
      }
      const box = el("div", "agents");
      for (const p of items) {
        const c = el("div", "agent");
        c.append(el("div", "agent-name", p.descripcion));
        if (p.contexto) c.append(el("div", "muted", "de: " + p.contexto));
        if (p.tipo) c.append(el("span", "badge", p.tipo));
        box.append(c);
      }
      this.body.append(box);
    } catch (e) {
      this.error(e);
    }
  }

  // --- Pestaña YAML crudo ---
  private async renderRaw() {
    this.body.replaceChildren();
    const bar = el("div", "raw-bar");
    const sel = el("select", "field");
    for (const w of ["teams", "models", "tools", "prompts"]) {
      const o = el("option", undefined, w + ".yaml");
      o.value = w;
      sel.append(o);
    }
    const ta = el("textarea", "raw-area") as HTMLTextAreaElement;
    ta.spellcheck = false;
    const save = el("button", "btn", "Guardar");
    bar.append(sel, save);
    this.body.append(bar, ta);

    const cargar = async () => {
      ta.value = "Cargando…";
      try {
        const r = await api("GET", `/api/config/raw/${sel.value}`);
        ta.value = r.text;
      } catch (e) {
        ta.value = "Error: " + (e as Error).message;
      }
    };
    sel.onchange = cargar;
    save.onclick = async () => {
      save.disabled = true;
      try {
        await api("PUT", `/api/config/raw/${sel.value}`, { text: ta.value });
        this.aviso(`${sel.value}.yaml guardado ✓`);
      } catch (e) {
        this.aviso((e as Error).message, false);
      }
      save.disabled = false;
    };
    await cargar();
  }
}
