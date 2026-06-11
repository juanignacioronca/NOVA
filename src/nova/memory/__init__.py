"""Memoria de largo plazo de NOVA (todo local, $0).

Dos capas que se espejan:
- **Motor** (`store.py`, SQLite): grafo (nodos + aristas) + vectores (embeddings)
  para consultas rápidas — semántico (coseno) y por relaciones (grafo, multi-hop).
- **Bóveda Obsidian** (`obsidian.py`): una nota `.md` por entidad con `[[wikilinks]]`,
  navegable por humano; la estructura de links espeja el grafo.

El `WorldState` sigue siendo el **caché vivo** de esta memoria. Privacidad: todo
local; nunca se guardan claves/credenciales (ver CLAUDE.md §11).
"""

from .embeddings import Embedder, stub_embed
from .extractor import Extractor
from .obsidian import ObsidianVault
from .store import MemoryStore, Nodo

__all__ = ["MemoryStore", "Nodo", "Embedder", "stub_embed", "Extractor", "ObsidianVault"]
