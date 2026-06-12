"""Extractor: de un turno (conversación/registro) saca **entidades + relaciones +
hechos** y los escribe al store + crea/actualiza las notas Obsidian.

Modelo (`memoria_contexto`) → JSON con parseo tolerante; en stub, **heurística**.
Acota el tamaño de lo extraído. El contenido externo (de tools) ya viene marcado
no confiable antes de llegar acá (ver CLAUDE.md §11).
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from ..core import prompts
from ..models import model_router
from .embeddings import _norm, tokens
from .obsidian import ObsidianVault
from .store import MemoryStore

# Parentescos → etiqueta canónica (claves normalizadas, sin acento).
KINSHIP = {
    "papa": "Papá", "mama": "Mamá", "hermano": "Hermano", "hermana": "Hermana",
    "jefe": "Jefe", "novia": "Novia", "novio": "Novio", "abuelo": "Abuelo", "abuela": "Abuela",
    "tio": "Tío", "tia": "Tía", "primo": "Primo", "prima": "Prima",
}
_PREF_RE = re.compile(r"(?:prefiero|me gustan|me gusta|odio|no me gusta)\s+(.+)", re.IGNORECASE)
_LISTA_RE = re.compile(r"lista\s+(?:de\s+la\s+|del\s+|de\s+)?([a-z]+)")

# Muestreo determinista para extraer (JSON con modelo chico local).
_OPTS_EXTRACT = {"temperature": 0.1, "max_tokens": 500, "response_format": {"type": "json_object"}}


class Extractor:
    def __init__(self, store: MemoryStore, obsidian: Optional[ObsidianVault] = None,
                 model_key: str = "memoria_contexto", max_entidades: int = 8) -> None:
        self.store = store
        self.obsidian = obsidian
        self.model_key = model_key
        self.max_entidades = max_entidades

    async def extraer(self, texto: str, fuente: str = "conversacion") -> Dict[str, Any]:
        if not texto or not texto.strip() or not self._vale_la_pena(texto):
            return {"entidades": [], "relaciones": [], "ids": []}
        data = await self._extraer_datos(texto)
        ids = await self._persistir(data, texto)
        if self.obsidian is not None:
            for nid in ids:
                try:
                    await self.obsidian.escribir(self.store, nid)
                except Exception:
                    pass  # nunca romper por una nota
        return {"entidades": [e["nombre"] for e in data["entidades"]], "relaciones": data["relaciones"], "ids": ids}

    @staticmethod
    def _vale_la_pena(texto: str) -> bool:
        """Filtra los turnos que no aportan memoria (saludos, "ok", "sí").

        Antes, CADA turno terminaba como nodo "hecho" — incluso "hola" — y ese
        ruido volvía por el recall al prompt del modelo (alucinaciones).
        """
        from ..core.comprension import es_smalltalk  # import tardío (evita ciclo)

        if es_smalltalk(texto):
            return False
        return len(tokens(texto)) >= 3

    async def _extraer_datos(self, texto: str) -> Dict[str, Any]:
        comp = await model_router.complete_meta(self.model_key,
            [{"role": "system", "content": prompts.get("extractor")}, {"role": "user", "content": texto}],
            **_OPTS_EXTRACT)
        if not comp.text.startswith("[stub:"):
            data = self._parse(comp.text)
            if data is not None:
                return data
        return self._heuristica(texto)

    def _parse(self, text: str) -> Optional[Dict[str, Any]]:
        ini, fin = text.find("{"), text.rfind("}")
        if ini == -1 or fin <= ini:
            return None
        try:
            d = json.loads(text[ini:fin + 1])
        except (json.JSONDecodeError, ValueError):
            return None
        if not isinstance(d, dict):
            return None
        d.setdefault("entidades", [])
        d.setdefault("relaciones", [])
        return d

    def _heuristica(self, texto: str) -> Dict[str, Any]:
        norm = _norm(texto)
        toks = set(tokens(texto))
        entidades: List[dict] = []
        relaciones: List[dict] = []

        # Personas por parentesco.
        personas = {}
        for clave, label in KINSHIP.items():
            if clave in toks:
                personas[clave] = label
                entidades.append({"tipo": "persona", "nombre": label, "props": {}})

        # Preferencia.
        m = _PREF_RE.search(texto)
        if m:
            objeto = re.split(r"\s+para\s+|[.,;:]", m.group(1).strip())[0].strip()
            if objeto:
                entidades.append({"tipo": "preferencia", "nombre": objeto, "props": {"frase": texto.strip()}, "texto": texto.strip()})

        # Tarea / lista (ligada a la persona si la nombra).
        if "lista" in toks or "comprar" in toks or "tengo que" in norm or "recordar" in toks:
            lm = _LISTA_RE.search(norm)
            persona_label = KINSHIP.get(lm.group(1)) if lm else None
            nombre = f"lista del {persona_label}" if persona_label else (texto.strip()[:40] or "tarea")
            entidades.append({"tipo": "tarea", "nombre": nombre, "props": {"detalle": texto.strip()}})
            if persona_label:
                relaciones.append({"src_tipo": "tarea", "src_nombre": nombre, "tipo": "de", "dst_tipo": "persona", "dst_nombre": persona_label})

        # Siempre: un hecho con el turno (queda recuperable por semántica).
        entidades.append({"tipo": "hecho", "nombre": texto.strip()[:48], "props": {}, "texto": texto.strip()})
        return {"entidades": entidades, "relaciones": relaciones}

    async def _persistir(self, data: Dict[str, Any], texto: str) -> List[str]:
        idmap: Dict[tuple, str] = {}
        afectados: List[str] = []
        for e in (data.get("entidades") or [])[: self.max_entidades]:
            tipo, nombre = str(e.get("tipo", "hecho")), str(e.get("nombre", "")).strip()
            if not nombre:
                continue
            nid = await self.store.add_nodo(tipo, nombre, e.get("props"), e.get("texto") or texto)
            idmap[(tipo, nombre)] = nid
            afectados.append(nid)
        for r in data.get("relaciones") or []:
            src = idmap.get((r.get("src_tipo"), r.get("src_nombre"))) or self.store.node_id(str(r.get("src_tipo")), str(r.get("src_nombre")))
            dst = idmap.get((r.get("dst_tipo"), r.get("dst_nombre"))) or self.store.node_id(str(r.get("dst_tipo")), str(r.get("dst_nombre")))
            await self.store.add_arista(src, dst, str(r.get("tipo", "rel")))
            afectados += [src, dst]
        return list(dict.fromkeys(afectados))
