"""Capa Obsidian: una nota `.md` por entidad, con frontmatter + `[[wikilinks]]`
a las entidades relacionadas (la estructura de links espeja el grafo). NOVA la
mantiene sincronizada desde el store; se deja la opción de re-ingerir ediciones.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..paths import vault_dir
from .store import MemoryStore, Nodo, slug


class ObsidianVault:
    def __init__(self, directorio=None) -> None:
        self.dir = Path(directorio or vault_dir())

    def nota_path(self, nodo: Nodo) -> Path:
        return self.dir / f"{slug(nodo.nombre)}.md"

    async def escribir(self, store: MemoryStore, nid: str) -> Optional[Path]:
        """(Re)escribe la nota de un nodo con sus relaciones como wikilinks."""
        nodo = await store.get_nodo(nid)
        if nodo is None:
            return None
        rels = await store.relaciones(nid)
        self.dir.mkdir(parents=True, exist_ok=True)

        fm = [
            "---",
            f"id: {nodo.id}",
            f"tipo: {nodo.tipo}",
            f"nombre: {nodo.nombre}",
            f"actualizado: {datetime.now().isoformat(timespec='seconds')}",
            "---",
            "",
            f"# {nodo.nombre}",
            "",
        ]
        if nodo.props:
            fm.append("## Datos")
            for k, v in nodo.props.items():
                fm.append(f"- **{k}:** {v}")
            fm.append("")
        if rels:
            fm.append("## Relaciones")
            for r in rels:
                flecha = "→" if r["direccion"] == "out" else "←"
                fm.append(f"- {flecha} ({r['tipo']}) [[{r['otro'].nombre}]]")
            fm.append("")

        path = self.nota_path(nodo)
        path.write_text("\n".join(fm), encoding="utf-8")
        return path

    async def sincronizar(self, store: MemoryStore) -> int:
        """Reescribe todas las notas desde el store. Devuelve cuántas escribió."""
        nodos = await store.all_nodos()
        for nodo in nodos:
            await self.escribir(store, nodo.id)
        return len(nodos)

    def reingerir(self):  # pragma: no cover - re-ingesta avanzada = futuro
        """Punto de extensión: re-ingerir ediciones humanas del vault al store.
        La re-ingesta avanzada (parseo de frontmatter/links editados) es futuro."""
        raise NotImplementedError("re-ingesta de ediciones humanas: futuro")
