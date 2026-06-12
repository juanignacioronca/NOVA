// Modo configuración: editor del roster de NOVA contra /api/config/*.
//  - Pestaña "Agentes": por equipo, cada sub-agente con su PROMPT (rol), su modelo,
//    sus herramientas y a quién puede consultar. Crear / borrar agentes.
//  - Pestaña "YAML crudo": el texto completo de teams/models/tools (power-user).
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
    head.append(el("h2", undefined, "Configuración del roster"));
    const tabs = el("div", "config-tabs");
    const tabA = el("button", "ctab active", "Agentes");
    const tabP = el("button", "ctab", "Pendientes");
    const tabY = el("button", "ctab", "YAML crudo");
    tabs.append(tabA, tabP, tabY);
    head.append(tabs);
    this.toast = el("div", "config-toast");
    this.body = el("div", "config-body");
    this.el.append(head, this.toast, this.body);

    const activar = (b: HTMLElement) => {
      for (const t of [tabA, tabP, tabY]) t.classList.toggle("active", t === b);
    };
    tabA.onclick = () => { activar(tabA); this.renderAgentes(); };
    tabP.onclick = () => { activar(tabP); this.renderPendientes(); };
    tabY.onclick = () => { activar(tabY); this.renderRaw(); };
  }

  private aviso(txt: string, ok = true) {
    this.toast.textContent = txt;
    this.toast.classList.toggle("err", !ok);
    this.toast.classList.add("show");
    setTimeout(() => this.toast.classList.remove("show"), 2600);
  }

  async abrir() {
    this.el.hidden = false;
    await this.renderAgentes();
  }
  cerrar() {
    this.el.hidden = true;
  }

  // --- Pestaña Agentes ---
  private async renderAgentes() {
    this.body.replaceChildren(el("div", "muted", "Cargando…"));
    try {
      const [ag, mods] = await Promise.all([
        api("GET", "/api/config/agents"),
        api("GET", "/api/config/models"),
      ]);
      this.modelos = mods.models || [];
      this.allTools = ag.all_tools || [];
      this.body.replaceChildren();
      for (const eq of ag.teams as Equipo[]) this.body.append(this.equipoCard(eq));
    } catch (e) {
      this.body.replaceChildren(el("div", "config-toast err show", "Error: " + (e as Error).message));
    }
  }

  private equipoCard(eq: Equipo): HTMLElement {
    const wrap = el("div", "team");
    const h = el("div", "team-h");
    h.append(el("span", "team-name", eq.id), el("span", "badge", eq.tipo));
    const addBtn = el("button", "btn ghost", "+ agente");
    addBtn.onclick = () => this.nuevoAgente(eq.id, wrap, agentsBox);
    h.append(addBtn);
    const agentsBox = el("div", "agents");
    for (const sa of eq.sub_agentes) agentsBox.append(this.agenteCard(eq.id, sa));
    wrap.append(h, agentsBox);
    return wrap;
  }

  private modeloSelect(actual: string): HTMLSelectElement {
    const sel = el("select", "field");
    const opciones = this.modelos.includes(actual)
      ? this.modelos
      : [actual, ...this.modelos];
    for (const m of opciones) {
      const o = el("option", undefined, m);
      o.value = m;
      if (m === actual) o.selected = true;
      sel.append(o);
    }
    return sel;
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

    const lista = (s: string) =>
      s.split(",").map((x) => x.trim()).filter(Boolean);

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

  private async nuevoAgente(team: string, _wrap: HTMLElement, box: HTMLElement) {
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

  // --- Pestaña Pendientes (lo que NOVA no pudo hacer / datos que le faltan) ---
  private async renderPendientes() {
    this.body.replaceChildren(el("div", "muted", "Cargando…"));
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
      this.body.replaceChildren(el("div", "config-toast err show", "Error: " + (e as Error).message));
    }
  }

  // --- Pestaña YAML crudo ---
  private async renderRaw() {
    this.body.replaceChildren();
    const bar = el("div", "raw-bar");
    const sel = el("select", "field");
    for (const w of ["teams", "models", "tools"]) {
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
