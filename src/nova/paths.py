"""Rutas canónicas del proyecto, estables sin importar el cwd."""

from __future__ import annotations

import os
from pathlib import Path

# .../src/nova/paths.py -> PACKAGE_ROOT = .../src/nova
PACKAGE_ROOT: Path = Path(__file__).resolve().parent
# .../src/nova -> parents[0]=.../src -> parents[1]=raíz del repo (o site-packages)
PROJECT_ROOT: Path = PACKAGE_ROOT.parents[1]

CONFIG_DIR: Path = PACKAGE_ROOT / "config"
MODELS_YAML: Path = CONFIG_DIR / "models.yaml"
PERCEPTION_YAML: Path = CONFIG_DIR / "perception.yaml"
TOOLS_YAML: Path = CONFIG_DIR / "tools.yaml"
TEAMS_YAML: Path = CONFIG_DIR / "teams.yaml"
EMPRESA_YAML: Path = CONFIG_DIR / "empresa.yaml"
PROMPTS_YAML: Path = CONFIG_DIR / "prompts.yaml"
# Logs: por defecto `<repo>/logs`, overridable con NOVA_LOG_DIR (Docker monta
# un volumen escribible ahí, ya que el resto del filesystem es read-only).
LOGS_DIR: Path = Path(os.environ.get("NOVA_LOG_DIR", str(PROJECT_ROOT / "logs")))
ENV_FILE: Path = PROJECT_ROOT / ".env"


def data_dir() -> Path:
    """Carpeta de datos locales (calendario, memoria, etc.). Overridable con
    NOVA_DATA_DIR. Se lee en cada llamada para respetar overrides por test/runtime.
    """
    return Path(os.environ.get("NOVA_DATA_DIR", str(PROJECT_ROOT / "data")))


def memory_db() -> Path:
    """Archivo SQLite del motor de memoria (grafo + vectores)."""
    return data_dir() / "memory.db"


def vault_dir() -> Path:
    """Bóveda Obsidian (carpeta de notas `.md` navegables)."""
    return data_dir() / "vault"
