"""Rutas canónicas del proyecto, estables sin importar el cwd."""

from __future__ import annotations

from pathlib import Path

# .../src/nova/paths.py -> PACKAGE_ROOT = .../src/nova
PACKAGE_ROOT: Path = Path(__file__).resolve().parent
# .../src/nova -> parents[0]=.../src -> parents[1]=raíz del repo
PROJECT_ROOT: Path = PACKAGE_ROOT.parents[1]

CONFIG_DIR: Path = PACKAGE_ROOT / "config"
MODELS_YAML: Path = CONFIG_DIR / "models.yaml"
LOGS_DIR: Path = PROJECT_ROOT / "logs"
ENV_FILE: Path = PROJECT_ROOT / ".env"
