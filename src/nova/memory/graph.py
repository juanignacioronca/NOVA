"""Traversal del grafo de memoria. Usa `networkx` si está; si no, BFS en Python
puro (los tests corren sin instalar nada extra).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Set


def _adyacencia(aristas: List[dict]) -> Dict[str, Set[str]]:
    adj: Dict[str, Set[str]] = defaultdict(set)
    for a in aristas:
        s, d = a.get("src"), a.get("dst")
        if s and d:
            adj[s].add(d)
            adj[d].add(s)  # tratamos el grafo como no dirigido para el traversal
    return adj


def multi_hop(aristas: List[dict], start: str, profundidad: int = 2) -> List[str]:
    """IDs alcanzables desde `start` hasta `profundidad` saltos (sin incluirlo)."""
    try:
        import networkx as nx

        g = nx.Graph()
        for a in aristas:
            if a.get("src") and a.get("dst"):
                g.add_edge(a["src"], a["dst"])
        if start not in g:
            return []
        largos = nx.single_source_shortest_path_length(g, start, cutoff=profundidad)
        return [n for n, dist in largos.items() if 0 < dist <= profundidad]
    except ImportError:
        adj = _adyacencia(aristas)
        vistos = {start}
        frontera = {start}
        salida: List[str] = []
        for _ in range(max(0, profundidad)):
            siguiente: Set[str] = set()
            for nodo in frontera:
                for vecino in adj.get(nodo, ()):
                    if vecino not in vistos:
                        vistos.add(vecino)
                        siguiente.add(vecino)
                        salida.append(vecino)
            frontera = siguiente
        return salida
