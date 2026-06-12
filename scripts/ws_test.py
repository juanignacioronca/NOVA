"""Prueba rápida del WS: manda un texto y revisa que llegue `voz` (para que el
navegador hable). Uso: python scripts/ws_test.py"""
import asyncio
import json
import sys

import websockets


async def main() -> int:
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri, max_size=8 * 1024 * 1024) as ws:
        await ws.send(json.dumps({"type": "text", "text": "contame un dato curioso corto"}))
        tipos = []
        voz_frases = None
        try:
            for _ in range(40):
                raw = await asyncio.wait_for(ws.recv(), timeout=30)
                m = json.loads(raw)
                t = m.get("type")
                tipos.append(t)
                if t == "voz":
                    voz_frases = m.get("frases")
                if t == "answer":
                    print("ANSWER:", m.get("text", "")[:80])
                    break
        except asyncio.TimeoutError:
            print("timeout")
        print("tipos recibidos:", tipos)
        print("voz frases:", voz_frases)
        return 0 if voz_frases else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
