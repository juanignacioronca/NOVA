"""Modo configuración: API para ver y editar el roster de NOVA en caliente.

Expone, bajo `/api/config/*`:
- **Editor estructurado de agentes** (lo más usado): listar los sub-agentes de
  cada equipo (`teams.yaml`), editar su *prompt* (`rol`), su modelo (spec en
  `models.yaml`), sus herramientas y a quién pueden consultar; crear y borrar.
- **Editor crudo** (power-user): el texto YAML completo de `teams`/`models`/`tools`
  con validación + backup `.bak` antes de guardar.
- **Modelos disponibles**: tags de Ollama (GPU local) + specs ya usados, para los
  desplegables del editor.

Seguridad: pensado para LAN/Tailscale (no WAN). Cada guardado valida el YAML, hace
backup y recarga la config del router en memoria (los equipos se releen por request).
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .paths import MODELS_YAML, PROMPTS_YAML, TEAMS_YAML, TOOLS_YAML

router = APIRouter(prefix="/api/config", tags=["config"])

_FILES = {"teams": TEAMS_YAML, "models": MODELS_YAML, "tools": TOOLS_YAML, "prompts": PROMPTS_YAML}


# --- YAML round-trip (preserva comentarios si ruamel está disponible) ----------
try:  # ruamel mantiene comentarios y orden al reescribir
    from ruamel.yaml import YAML as _RuamelYAML

    _ruamel = _RuamelYAML()
    _ruamel.preserve_quotes = True
    _ruamel.indent(mapping=2, sequence=4, offset=2)
    _ruamel.width = 4096

    def _load(path) -> Any:
        with open(path, "r", encoding="utf-8") as fh:
            return _ruamel.load(fh) or {}

    def _dump(path, data) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            _ruamel.dump(data, fh)

except Exception:  # pragma: no cover - fallback a PyYAML (pierde comentarios)
    def _load(path) -> Any:
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    def _dump(path, data) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)


def _read_text(path) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _backup(path) -> None:
    """Copia `archivo.yaml` → `archivo.yaml.bak` antes de sobrescribir."""
    try:
        shutil.copy2(path, str(path) + ".bak")
    except OSError:
        pass


def _reload_router() -> None:
    """Recarga la config del model_router en memoria (models.yaml cacheado)."""
    try:
        from .models.model_router import load_config

        load_config(force=True)
    except Exception:
        pass


# --- modelos disponibles (para los desplegables) -------------------------------
async def _ollama_models() -> List[str]:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=2.0) as cli:
            r = await cli.get(host + "/api/tags")
            r.raise_for_status()
            return [f"ollama:{m['name']}" for m in r.json().get("models", [])]
    except Exception:
        return []


def _specs_en_uso() -> List[str]:
    """Specs ya presentes en models.yaml (string o lista)."""
    cfg = _load(MODELS_YAML)
    out: List[str] = []
    for val in (cfg.get("agents") or {}).values():
        if isinstance(val, str):
            out.append(val)
        elif isinstance(val, (list, tuple)):
            out.extend(str(v) for v in val)
    d = cfg.get("defaults") or {}
    if d.get("fallback"):
        out.append(str(d["fallback"]))
    return out


@router.get("/models")
async def modelos_disponibles() -> dict:
    """Lista de specs `proveedor:modelo` para elegir en el editor."""
    ollama = await _ollama_models()
    cloud = [
        "gemini:gemini-2.5-flash",
        "groq:llama-3.3-70b-versatile",
        "openrouter:deepseek/deepseek-r1:free",
    ]
    # únicos preservando orden: ollama (GPU local) primero, luego nube, luego en uso
    vistos: Dict[str, None] = {}
    for s in ollama + cloud + _specs_en_uso():
        vistos.setdefault(s, None)
    return {"models": list(vistos.keys()), "ollama": ollama, "cloud": cloud}


# --- editor estructurado de agentes -------------------------------------------
def _models_map() -> Dict[str, Any]:
    return _load(MODELS_YAML).get("agents") or {}


def _spec_de(model_key: str) -> str:
    """Spec textual del `model_key` (primer elemento si es lista de fallback)."""
    val = _models_map().get(model_key)
    if isinstance(val, str):
        return val
    if isinstance(val, (list, tuple)) and val:
        return str(val[0])
    return ""


def _model_key_compartido(model_key: str) -> int:
    """Cuántos sub-agentes (en teams.yaml) usan este model_key."""
    teams = _load(TEAMS_YAML).get("equipos") or {}
    n = 0
    for eq in teams.values():
        for sa in eq.get("sub_agentes") or []:
            if sa.get("model_key") == model_key:
                n += 1
    return n


@router.get("/agents")
async def listar_agentes() -> dict:
    """Vista estructurada: equipos → sub-agentes con prompt, modelo y skills."""
    teams = _load(TEAMS_YAML).get("equipos") or {}
    tools_cfg = _load(TOOLS_YAML)
    allowlist = list(tools_cfg.get("allowlist") or [])
    out_teams = []
    for team_id, eq in teams.items():
        subs = []
        for sa in eq.get("sub_agentes") or []:
            mk = sa.get("model_key", "")
            subs.append(
                {
                    "name": sa.get("name", ""),
                    "rol": sa.get("rol", ""),
                    "model_key": mk,
                    "model_spec": _spec_de(mk),
                    "model_compartido": _model_key_compartido(mk),
                    "tools": list(sa.get("tools") or []),
                    "puede_consultar": list(sa.get("puede_consultar") or []),
                }
            )
        out_teams.append(
            {
                "id": team_id,
                "tipo": eq.get("tipo", ""),
                "lider": eq.get("lider"),
                "sub_agentes": subs,
            }
        )
    return {"teams": out_teams, "all_tools": allowlist}


class AgentPatch(BaseModel):
    rol: Optional[str] = None
    model_spec: Optional[str] = None
    tools: Optional[List[str]] = None
    puede_consultar: Optional[List[str]] = None


class AgentNew(BaseModel):
    name: str
    rol: str = ""
    model_spec: str = ""
    tools: List[str] = []
    puede_consultar: List[str] = []


def _find_sub(teams_data, team_id, name):
    eq = (teams_data.get("equipos") or {}).get(team_id)
    if eq is None:
        raise HTTPException(404, f"equipo '{team_id}' no existe")
    for sa in eq.get("sub_agentes") or []:
        if sa.get("name") == name:
            return eq, sa
    raise HTTPException(404, f"agente '{name}' no existe en '{team_id}'")


def _set_spec(model_key: str, spec: str) -> None:
    """Escribe la spec bajo el model_key en models.yaml (crea la clave si falta)."""
    if not model_key or not spec:
        return
    data = _load(MODELS_YAML)
    agents = data.setdefault("agents", {})
    agents[model_key] = spec
    _backup(MODELS_YAML)
    _dump(MODELS_YAML, data)
    _reload_router()


@router.put("/agents/{team_id}/{name}")
async def editar_agente(team_id: str, name: str, patch: AgentPatch) -> dict:
    data = _load(TEAMS_YAML)
    _eq, sa = _find_sub(data, team_id, name)
    if patch.rol is not None:
        sa["rol"] = patch.rol
    if patch.tools is not None:
        sa["tools"] = patch.tools
    if patch.puede_consultar is not None:
        sa["puede_consultar"] = patch.puede_consultar
    _backup(TEAMS_YAML)
    _dump(TEAMS_YAML, data)
    aviso = None
    if patch.model_spec:
        mk = sa.get("model_key", "")
        comp = _model_key_compartido(mk)
        _set_spec(mk, patch.model_spec)
        if comp > 1:
            aviso = f"El modelo '{mk}' lo comparten {comp} agentes; el cambio los afecta a todos."
    return {"ok": True, "aviso": aviso}


@router.post("/agents/{team_id}")
async def crear_agente(team_id: str, nuevo: AgentNew) -> dict:
    data = _load(TEAMS_YAML)
    eq = (data.get("equipos") or {}).get(team_id)
    if eq is None:
        raise HTTPException(404, f"equipo '{team_id}' no existe")
    subs = eq.setdefault("sub_agentes", [])
    if any(sa.get("name") == nuevo.name for sa in subs):
        raise HTTPException(409, f"ya existe un agente '{nuevo.name}'")
    model_key = nuevo.name  # cada agente nuevo estrena su propia clave de modelo
    subs.append(
        {
            "name": nuevo.name,
            "rol": nuevo.rol,
            "model_key": model_key,
            "tools": nuevo.tools,
            "puede_consultar": nuevo.puede_consultar,
        }
    )
    _backup(TEAMS_YAML)
    _dump(TEAMS_YAML, data)
    _set_spec(model_key, nuevo.model_spec or "ollama:qwen2.5:7b")
    return {"ok": True}


@router.delete("/agents/{team_id}/{name}")
async def borrar_agente(team_id: str, name: str) -> dict:
    data = _load(TEAMS_YAML)
    eq = (data.get("equipos") or {}).get(team_id)
    if eq is None:
        raise HTTPException(404, f"equipo '{team_id}' no existe")
    subs = eq.get("sub_agentes") or []
    nuevos = [sa for sa in subs if sa.get("name") != name]
    if len(nuevos) == len(subs):
        raise HTTPException(404, f"agente '{name}' no existe en '{team_id}'")
    eq["sub_agentes"] = nuevos
    _backup(TEAMS_YAML)
    _dump(TEAMS_YAML, data)
    return {"ok": True}


# --- prompts del sistema (editables, con default de fábrica) -------------------
class PromptIn(BaseModel):
    text: str


@router.get("/prompts")
async def listar_prompts() -> dict:
    """Todos los prompts del sistema: texto vigente + si es el default o un override."""
    from .core import prompts

    return {"prompts": prompts.listar()}


@router.put("/prompts/{name}")
async def guardar_prompt(name: str, body: PromptIn) -> dict:
    """Guarda el override de un prompt (texto vacío o igual al default = volver al default)."""
    from .core import prompts

    try:
        prompts.set_override(name, body.text)
    except KeyError:
        raise HTTPException(404, f"prompt '{name}' no existe")
    return {"ok": True, "es_default": name not in prompts.load()}


# --- modelos del núcleo (models.yaml, fuera de teams.yaml) ----------------------
_CORE_DESC = {
    "conductor_simple": "Clasifica cada mensaje y responde lo simple (corre SIEMPRE, local)",
    "conductor_complex": "Sintetiza la respuesta final de lo complejo",
    "conductor_vision": "Mensajes con imagen del usuario",
    "respuestas_rapidas": "Agente local de respuestas cortas",
    "memoria_contexto": "Extrae recuerdos de cada turno (local)",
    "sentinela_vision": "Describe lo que ve la cámara (local-first)",
}


@router.get("/core")
async def core_models() -> dict:
    """Mapa agente→modelo de models.yaml (el roster del núcleo) para el editor."""
    cfg = _load(MODELS_YAML)
    agents = cfg.get("agents") or {}
    out = []
    for key, val in agents.items():
        if isinstance(val, (list, tuple)):
            cadena = [str(v) for v in val]
        else:
            cadena = [str(val)]
        out.append(
            {
                "key": str(key),
                "spec": cadena[0] if cadena else "",
                "cadena": cadena,
                "descripcion": _CORE_DESC.get(str(key), ""),
            }
        )
    fallback = str((cfg.get("defaults") or {}).get("fallback", ""))
    return {"agents": out, "fallback": fallback}


class CoreIn(BaseModel):
    spec: str


@router.put("/core/{key}")
async def set_core_model(key: str, body: CoreIn) -> dict:
    """Cambia el modelo primario de una clave de models.yaml (en caliente)."""
    spec = body.spec.strip()
    if ":" not in spec:
        raise HTTPException(400, "spec inválida: usá 'proveedor:modelo' (ej. ollama:llama3.2:3b)")
    data = _load(MODELS_YAML)
    if key == "_fallback":
        data.setdefault("defaults", {})["fallback"] = spec
    else:
        agents = data.setdefault("agents", {})
        if key not in agents:
            raise HTTPException(404, f"clave '{key}' no existe en models.yaml")
        val = agents[key]
        if isinstance(val, list) and val:
            val[0] = spec  # conserva la cadena de fallback por-agente
        else:
            agents[key] = spec
    _backup(MODELS_YAML)
    _dump(MODELS_YAML, data)
    _reload_router()
    return {"ok": True}


# --- estado de proveedores (doctor para la UI) ----------------------------------
@router.get("/estado")
async def estado_proveedores() -> dict:
    """Chequeo en vivo de cada proveedor (¿clave? ¿responde? latencia) + modelos
    pulled en Ollama. Es lo que muestra la pestaña Estado de la UI."""
    from .doctor import PROVIDERS, _check
    from .models.providers.ollama_client import ollama_models

    resultados = []
    for name in PROVIDERS:
        try:
            resultados.append(await _check(name))
        except Exception as exc:  # un proveedor roto no tira el panel
            resultados.append({"name": name, "ok": False, "state": "error", "detail": str(exc)})
    try:
        tags = ollama_models()
    except Exception:
        tags = []
    return {"proveedores": resultados, "ollama_models": tags}


# --- editor crudo (YAML completo) ---------------------------------------------
class RawIn(BaseModel):
    text: str


# --- pendientes / capacidades faltantes (lo que NOVA anotó que no puede hacer) ---
@router.get("/pendientes")
async def ver_pendientes() -> dict:
    from .tools.pendientes import listar

    return {"pendientes": listar(incluir_resueltos=False)}


@router.get("/raw/{which}")
async def leer_raw(which: str) -> dict:
    path = _FILES.get(which)
    if path is None:
        raise HTTPException(404, f"config '{which}' no existe (teams|models|tools)")
    return {"which": which, "text": _read_text(path)}


@router.put("/raw/{which}")
async def guardar_raw(which: str, body: RawIn) -> dict:
    path = _FILES.get(which)
    if path is None:
        raise HTTPException(404, f"config '{which}' no existe (teams|models|tools)")
    try:
        yaml.safe_load(body.text)  # valida antes de tocar el archivo
    except yaml.YAMLError as e:
        raise HTTPException(400, f"YAML inválido: {e}")
    _backup(path)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body.text)
    if which == "models":
        _reload_router()
    if which == "prompts":
        from .core import prompts

        prompts.load(force=True)
    return {"ok": True, "guardado": datetime.now().isoformat(timespec="seconds")}
