"""Escritura de registros JSONL.

`Registro.log(...)` agrega **una línea JSON por acción** a
`logs/AAAA-MM-DD.jsonl`, con timestamp. Campos (ver CLAUDE.md §8):
`{ts, agente, grupo, tarea, decision, modelo, resultado_breve}`.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from ..paths import LOGS_DIR

_BRIEF_MAX = 240


class Registro:
    def __init__(self, base_dir: Optional[Union[str, Path]] = None) -> None:
        self.base_dir = Path(base_dir) if base_dir is not None else LOGS_DIR
        self.last_path: Optional[Path] = None

    def _path_for(self, when: datetime) -> Path:
        return self.base_dir / f"{when:%Y-%m-%d}.jsonl"

    def log(
        self,
        agente: str,
        grupo: str,
        tarea: str,
        decision: str,
        modelo: str,
        resultado_breve: str,
    ) -> Path:
        """Escribe una línea JSONL y devuelve la ruta del archivo del día."""
        now = datetime.now()
        brief = " ".join(str(resultado_breve).split())
        if len(brief) > _BRIEF_MAX:
            brief = brief[:_BRIEF_MAX].rstrip() + "…"
        entry = {
            "ts": now.isoformat(timespec="seconds"),
            "agente": agente,
            "grupo": grupo,
            "tarea": tarea,
            "decision": decision,
            "modelo": modelo,
            "resultado_breve": brief,
        }
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self._path_for(now)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self.last_path = path
        return path


# Instancia por defecto + atajo de módulo.
_default = Registro()


def log(
    agente: str,
    grupo: str,
    tarea: str,
    decision: str,
    modelo: str,
    resultado_breve: str,
) -> Path:
    """Atajo: escribe con el `Registro` por defecto (`logs/` en la raíz)."""
    return _default.log(agente, grupo, tarea, decision, modelo, resultado_breve)
