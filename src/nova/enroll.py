"""Enrolamiento de personas (cara/voz) → memoria local.

    python -m nova.enroll <nombre> --fotos <carpeta> [--voz <carpeta>]
    python -m nova.enroll <nombre> --borrar          # borra los biométricos

Convención sugerida: `personas/<nombre>/fotos/` y `personas/<nombre>/voz/`.
Los vectores quedan en el nodo de la persona en la memoria (todo LOCAL).
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import List

from .env import load_env
from .memory.store import MemoryStore
from .recognition.faces import FaceRecognizer
from .recognition.voices import VoiceRecognizer

_FOTO_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
_VOZ_EXT = {".wav", ".flac", ".ogg", ".mp3", ".m4a"}


def _muestras(carpeta: str, exts: set) -> List[str]:
    base = Path(carpeta)
    return sorted(str(p) for p in base.glob("*") if p.suffix.lower() in exts)


async def _run(args: argparse.Namespace) -> int:
    store = MemoryStore()
    if args.borrar:
        await FaceRecognizer(store).borrar(args.nombre)
        await VoiceRecognizer(store).borrar(args.nombre)
        print(f"🗑  Borré los biométricos de «{args.nombre}».")
        return 0

    if not args.fotos and not args.voz:
        print("Indicá --fotos <carpeta> y/o --voz <carpeta> (o --borrar).")
        return 2

    if args.fotos:
        fotos = _muestras(args.fotos, _FOTO_EXT)
        if not fotos:
            print(f"⚠ No encontré fotos en {args.fotos}")
        else:
            r = await FaceRecognizer(store).enrolar(args.nombre, fotos)
            print(f"👤 Cara enrolada: {args.nombre} ← {r['muestras']} foto(s) (dim {r['dim']}).")

    if args.voz:
        voces = _muestras(args.voz, _VOZ_EXT)
        if not voces:
            print(f"⚠ No encontré audios en {args.voz}")
        else:
            r = await VoiceRecognizer(store).enrolar(args.nombre, voces)
            print(f"🎙  Voz enrolada: {args.nombre} ← {r['muestras']} muestra(s) (dim {r['dim']}).")

    print("Listo. Biométricos guardados LOCALMENTE en la memoria (nunca a la nube).")
    return 0


def main() -> int:
    load_env()
    ap = argparse.ArgumentParser(prog="nova.enroll", description="Enrola una persona (cara/voz) en la memoria local.")
    ap.add_argument("nombre", help="nombre de la persona (etiqueta de la entidad)")
    ap.add_argument("--fotos", help="carpeta con fotos de la cara")
    ap.add_argument("--voz", help="carpeta con muestras de voz")
    ap.add_argument("--borrar", action="store_true", help="borra los biométricos de la persona")
    return asyncio.run(_run(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
