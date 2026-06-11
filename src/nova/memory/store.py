"""Motor de memoria: SQLite (un archivo). Grafo (`nodos` + `aristas`) + vectores
(embedding por nodo, blob). Búsqueda semántica por **coseno** (numpy si está,
si no Python puro). A escala personal alcanza de sobra; `sqlite-vec`/Qdrant son
optimización futura para escala.
"""

from __future__ import annotations

import asyncio
import json
import math
import re
import sqlite3
import time
import unicodedata
from array import array
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..paths import memory_db
from . import graph
from .embeddings import Embedder


@dataclass
class Nodo:
    id: str
    tipo: str
    nombre: str
    props: Dict[str, Any] = field(default_factory=dict)
    ts: float = 0.0


def slug(texto: str) -> str:
    d = unicodedata.normalize("NFD", (texto or "").lower())
    base = "".join(c for c in d if unicodedata.category(c) != "Mn")
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base or "nodo"


def _pack(vec: List[float]) -> bytes:
    return array("f", vec).tobytes()


def _unpack(blob: Optional[bytes]) -> List[float]:
    if not blob:
        return []
    a = array("f")
    a.frombytes(blob)
    return list(a)


def cosine(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    try:
        import numpy as np

        va, vb = np.asarray(a, dtype="float32"), np.asarray(b, dtype="float32")
        n = float(np.linalg.norm(va) * np.linalg.norm(vb))
        return float(va[: len(vb)] @ vb[: len(va)]) / n if n else 0.0
    except ImportError:
        m = min(len(a), len(b))
        dot = sum(a[i] * b[i] for i in range(m))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        return dot / (na * nb) if na and nb else 0.0


class MemoryStore:
    def __init__(self, path=None, embedder: Optional[Embedder] = None) -> None:
        self.path = str(path or memory_db())
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.embedder = embedder or Embedder()
        self._lock = asyncio.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS nodos (
              id TEXT PRIMARY KEY, tipo TEXT, nombre TEXT, props TEXT, embedding BLOB, ts REAL
            );
            CREATE TABLE IF NOT EXISTS aristas (
              src TEXT, dst TEXT, tipo TEXT, props TEXT, ts REAL,
              PRIMARY KEY (src, dst, tipo)
            );
            CREATE INDEX IF NOT EXISTS idx_nodos_tipo ON nodos(tipo);
            CREATE INDEX IF NOT EXISTS idx_aristas_src ON aristas(src);
            CREATE INDEX IF NOT EXISTS idx_aristas_dst ON aristas(dst);
            """
        )
        self._conn.commit()

    def node_id(self, tipo: str, nombre: str) -> str:
        return f"{tipo}:{slug(nombre)}"

    @staticmethod
    def _row_to_nodo(r: sqlite3.Row) -> Nodo:
        return Nodo(r["id"], r["tipo"], r["nombre"], json.loads(r["props"] or "{}"), r["ts"] or 0.0)

    # --- escritura ---
    async def add_nodo(self, tipo: str, nombre: str, props: Optional[dict] = None, texto: Optional[str] = None) -> str:
        nid = self.node_id(tipo, nombre)
        props = props or {}
        cuerpo = texto or f"{tipo} {nombre} " + " ".join(f"{k}: {v}" for k, v in props.items())
        emb = await self.embedder.embed(cuerpo)
        async with self._lock:
            # Merge de props (preserva lo existente, ej. vectores biométricos enrolados).
            row = self._conn.execute("SELECT props FROM nodos WHERE id=?", (nid,)).fetchone()
            merged = json.loads(row["props"] or "{}") if row else {}
            merged.update(props)
            self._conn.execute(
                "INSERT INTO nodos(id,tipo,nombre,props,embedding,ts) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET nombre=excluded.nombre, props=excluded.props, "
                "embedding=excluded.embedding, ts=excluded.ts",
                (nid, tipo, nombre, json.dumps(merged, ensure_ascii=False), _pack(emb), time.time()),
            )
            self._conn.commit()
        return nid

    async def add_arista(self, src: str, dst: str, tipo: str, props: Optional[dict] = None) -> None:
        async with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO aristas(src,dst,tipo,props,ts) VALUES(?,?,?,?,?)",
                (src, dst, tipo, json.dumps(props or {}, ensure_ascii=False), time.time()),
            )
            self._conn.commit()

    async def actualizar(self, nid: str, props: dict) -> None:
        async with self._lock:
            row = self._conn.execute("SELECT props FROM nodos WHERE id=?", (nid,)).fetchone()
            if row is None:
                return
            actual = json.loads(row["props"] or "{}")
            actual.update(props or {})
            self._conn.execute("UPDATE nodos SET props=?, ts=? WHERE id=?", (json.dumps(actual, ensure_ascii=False), time.time(), nid))
            self._conn.commit()

    async def eliminar(self, nid: str) -> None:
        async with self._lock:
            self._conn.execute("DELETE FROM nodos WHERE id=?", (nid,))
            self._conn.execute("DELETE FROM aristas WHERE src=? OR dst=?", (nid, nid))
            self._conn.commit()

    # --- lectura ---
    async def get_nodo(self, nid: str) -> Optional[Nodo]:
        async with self._lock:
            r = self._conn.execute("SELECT * FROM nodos WHERE id=?", (nid,)).fetchone()
        return self._row_to_nodo(r) if r else None

    async def all_nodos(self) -> List[Nodo]:
        async with self._lock:
            rows = self._conn.execute("SELECT * FROM nodos").fetchall()
        return [self._row_to_nodo(r) for r in rows]

    async def all_aristas(self) -> List[dict]:
        async with self._lock:
            rows = self._conn.execute("SELECT src,dst,tipo,props FROM aristas").fetchall()
        return [{"src": r["src"], "dst": r["dst"], "tipo": r["tipo"], "props": json.loads(r["props"] or "{}")} for r in rows]

    async def buscar_semantico(self, q: str, k: int = 5, tipo: Optional[str] = None) -> List[Tuple[Nodo, float]]:
        qv = await self.embedder.embed(q)
        async with self._lock:
            sql = "SELECT * FROM nodos" + (" WHERE tipo=?" if tipo else "")
            rows = self._conn.execute(sql, (tipo,) if tipo else ()).fetchall()
        puntuados = [(self._row_to_nodo(r), cosine(qv, _unpack(r["embedding"]))) for r in rows]
        puntuados.sort(key=lambda x: x[1], reverse=True)
        return [(n, s) for n, s in puntuados[:k] if s > 0]

    async def relaciones(self, nid: str) -> List[dict]:
        """Aristas incidentes a un nodo, con el otro extremo resuelto a Nodo."""
        async with self._lock:
            out = self._conn.execute("SELECT tipo,dst FROM aristas WHERE src=?", (nid,)).fetchall()
            inn = self._conn.execute("SELECT tipo,src FROM aristas WHERE dst=?", (nid,)).fetchall()
        rels = []
        for r in out:
            otro = await self.get_nodo(r["dst"])
            if otro:
                rels.append({"tipo": r["tipo"], "direccion": "out", "otro": otro})
        for r in inn:
            otro = await self.get_nodo(r["src"])
            if otro:
                rels.append({"tipo": r["tipo"], "direccion": "in", "otro": otro})
        return rels

    async def vecinos(self, nid: str, tipo: Optional[str] = None) -> List[Nodo]:
        rels = await self.relaciones(nid)
        return [r["otro"] for r in rels if tipo is None or r["tipo"] == tipo]

    async def multi_hop(self, nid: str, profundidad: int = 2) -> List[Nodo]:
        ids = graph.multi_hop(await self.all_aristas(), nid, profundidad)
        out = []
        for i in ids:
            n = await self.get_nodo(i)
            if n:
                out.append(n)
        return out

    def close(self) -> None:
        self._conn.close()
