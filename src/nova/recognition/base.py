"""Motor biométrico genérico (cara o voz): enrolar (promedio de embeddings) y
match (coseno) contra los nodos `persona` de la memoria. El embedder real es
inyectado por cada modalidad; si falta o `NOVA_FORCE_STUB`, usa un stub
determinista derivado de los bytes (tests offline).
"""

from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union

from ..memory.store import MemoryStore, cosine

Muestra = Union[str, bytes, "os.PathLike"]


def _leer(muestra: Muestra) -> bytes:
    if isinstance(muestra, (bytes, bytearray)):
        return bytes(muestra)
    p = Path(muestra)
    return p.read_bytes() if p.exists() else str(muestra).encode("utf-8")


def stub_vector(data: bytes, dim: int) -> List[float]:
    """Vector determinista derivado de los bytes (mismo input → mismo vector)."""
    out: List[float] = []
    seed = data or b"\x00"
    while len(out) < dim:
        seed = hashlib.sha256(seed).digest()
        for b in seed:
            out.append((b / 255.0) * 2 - 1)
            if len(out) >= dim:
                break
    n = math.sqrt(sum(x * x for x in out))
    return [x / n for x in out] if n else out


def promedio(vecs: List[List[float]]) -> List[float]:
    """Promedio L2-normalizado de varios embeddings (el vector enrolado)."""
    vecs = [v for v in vecs if v]
    if not vecs:
        return []
    dim = len(vecs[0])
    acc = [0.0] * dim
    for v in vecs:
        for i in range(min(dim, len(v))):
            acc[i] += v[i]
    acc = [x / len(vecs) for x in acc]
    n = math.sqrt(sum(x * x for x in acc))
    return [x / n for x in acc] if n else acc


def _force_stub() -> bool:
    return os.environ.get("NOVA_FORCE_STUB", "").lower() in ("1", "true", "yes")


class Biometrico:
    def __init__(
        self,
        store: MemoryStore,
        *,
        kind: str,
        props_key: str,
        embed_real: Callable[[bytes], List[float]],
        dim: int,
        umbral: float,
    ) -> None:
        self.store = store
        self.kind = kind
        self.key = props_key
        self.embed_real = embed_real
        self.dim = dim
        self.umbral = umbral

    def embeber(self, muestra: Muestra) -> List[float]:
        data = _leer(muestra)
        if _force_stub():
            return stub_vector(data, self.dim)
        try:
            return self.embed_real(data)
        except Exception:
            return stub_vector(data, self.dim)  # degrada offline / sin modelo

    async def enrolar(self, nombre: str, muestras: List[Muestra]) -> dict:
        """Embeb+promedia las muestras y guarda el vector en el nodo de la persona."""
        vecs = [self.embeber(m) for m in muestras]
        prom = promedio(vecs)
        if not prom:
            raise ValueError(f"{self.kind}: no hay muestras válidas para enrolar")
        nid = self.store.node_id("persona", nombre)
        if await self.store.get_nodo(nid) is None:
            await self.store.add_nodo("persona", nombre, texto=f"persona {nombre}")
        await self.store.actualizar(nid, {self.key: prom, f"{self.key}_n": len([v for v in vecs if v])})
        return {"nodo": nid, "muestras": len([v for v in vecs if v]), "dim": len(prom)}

    async def match(self, muestra: Union[Muestra, List[float]], umbral: Optional[float] = None) -> Tuple[str, float]:
        """Devuelve (nombre, confianza). Bajo umbral → 'desconocido'."""
        u = self.umbral if umbral is None else umbral
        qv = muestra if isinstance(muestra, list) else self.embeber(muestra)  # type: ignore[arg-type]
        mejor, score = "desconocido", 0.0
        for nodo in await self.store.all_nodos():
            if nodo.tipo != "persona":
                continue
            vec = nodo.props.get(self.key)
            if not vec:
                continue
            s = cosine(qv, vec)
            if s > score:
                score, mejor = s, nodo.nombre
        return (mejor if score >= u else "desconocido"), round(score, 3)

    async def borrar(self, nombre: str) -> None:
        """Borra los biométricos de una persona (privacidad)."""
        nid = self.store.node_id("persona", nombre)
        if await self.store.get_nodo(nid) is not None:
            await self.store.actualizar(nid, {self.key: None, f"{self.key}_n": 0})
