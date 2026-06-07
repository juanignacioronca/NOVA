"""Cargador mínimo de `.env` (sin dependencias externas).

Las claves van en `.env` (bóveda de secretos, ver CLAUDE.md §5) y NUNCA en el
código. Este loader lee pares `KEY=VALUE` y los coloca en `os.environ` sin pisar
variables ya definidas en el entorno.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .paths import ENV_FILE


def load_env(path: Optional[Path] = None, override: bool = False) -> dict:
    """Carga variables desde un archivo `.env`. Devuelve lo cargado.

    Líneas vacías y las que empiezan con `#` se ignoran. No falla si el archivo
    no existe (el esqueleto corre sin `.env`).
    """
    env_path = path or ENV_FILE
    loaded: dict = {}
    if not env_path.exists():
        return loaded

    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = value
        loaded[key] = value
    return loaded
