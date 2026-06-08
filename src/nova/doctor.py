"""`python -m nova.doctor` — chequeo de proveedores de modelos.

Por cada proveedor con clave hace un `complete` mínimo y reporta estado +
latencia. Lista los modelos pulled en Ollama. No revienta si algo está caído.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Dict, List, Optional

from .env import load_env
from .models import model_router
from .models.providers.base import ProviderError
from .models.providers.ollama_client import ollama_models
from .models.providers.openai_compatible import provider_config

# Orden de chequeo (local primero).
PROVIDERS = ["ollama", "gemini", "groq", "openrouter", "deepseek"]

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"

PING = [{"role": "user", "content": "Responde solo con: OK"}]


async def _check(name: str) -> Dict[str, object]:
    cfg = provider_config(name)
    provider = model_router._get_provider(name)

    # Falta clave (los de nube): no chequear en vano.
    if cfg.key_env is not None and not os.environ.get(cfg.key_env, "").strip():
        return {"name": name, "ok": False, "state": "sin clave", "detail": f"falta {cfg.key_env}"}

    if provider is None or not provider.available():
        detail = "host no responde" if name == "ollama" else "no disponible"
        return {"name": name, "ok": False, "state": "no disponible", "detail": detail}

    model = model_router.sample_model(name)
    if not model:
        return {"name": name, "ok": False, "state": "sin modelo", "detail": "no hay modelo en models.yaml"}

    start = time.perf_counter()
    try:
        text = await provider.complete(model, PING, max_tokens=8, timeout=15.0)
        ms = int((time.perf_counter() - start) * 1000)
        return {"name": name, "ok": True, "state": "OK", "detail": f"{model} · {ms} ms · «{text[:40]}»"}
    except ProviderError as exc:
        ms = int((time.perf_counter() - start) * 1000)
        return {"name": name, "ok": False, "state": "error", "detail": f"{model} · {ms} ms · {exc}"}


def _line(result: Dict[str, object]) -> str:
    ok = bool(result["ok"])
    state = str(result["state"])
    if ok:
        color, mark = GREEN, "✓"
    elif state in ("sin clave", "no disponible", "sin modelo"):
        color, mark = YELLOW, "•"
    else:
        color, mark = RED, "✗"
    name = str(result["name"]).ljust(11)
    return f" {color}{mark} {name}{RESET} {state:<14} {DIM}{result['detail']}{RESET}"


async def _run() -> None:
    print("NOVA · doctor de proveedores")
    print("─" * 64)
    results: List[Dict[str, object]] = []
    for name in PROVIDERS:
        results.append(await _check(name))
    for result in results:
        print(_line(result))

    print("─" * 64)
    models = ollama_models()
    if models:
        print(f" Ollama · modelos pulled ({len(models)}):")
        for m in models:
            print(f"   - {m}")
    else:
        print(f" {YELLOW}Ollama sin modelos o no disponible{RESET} (¿`ollama serve` corriendo? ¿`ollama pull`?)")
    print("─" * 64)

    ok_real = [r for r in results if r["ok"] and r["name"] != "ollama"]
    if ok_real:
        print(f" {GREEN}Proveedor(es) en la nube OK:{RESET} " + ", ".join(str(r["name"]) for r in ok_real))
    else:
        print(f" {YELLOW}Sin proveedores en la nube{RESET} → NOVA usa local/stub. Cargá una clave en .env (ver .env.example).")


def main(argv: Optional[List[str]] = None) -> int:
    load_env()
    asyncio.run(_run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
