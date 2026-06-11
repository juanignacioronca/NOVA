"""Payload de presentación para el frontend (Prompt 9).

A partir del `last_run` del Conductor arma `{modalidad, proceso (traza), resultado
(contenido dinámico), texto, voz}`. El gestor de salidas lo manda por el WS y el
frontend lo renderiza: la **voz** narra/resume, la **pantalla** muestra el detalle
(complementarios). Pura/serializable → testeable offline.
"""

from __future__ import annotations

from typing import Any, Dict, List

MODALIDADES = ("voz", "pantalla", "ambos")


def construir_presentacion(run: Dict[str, Any], modalidad: str = "ambos") -> Dict[str, Any]:
    if modalidad not in MODALIDADES:
        modalidad = "ambos"
    resultado = _resultado(run)
    voz = _narracion(run) if modalidad in ("voz", "ambos") else ""
    return {
        "type": "presentacion",
        "modalidad": modalidad,
        "texto": run.get("final", ""),
        "voz": voz,
        "proceso": run.get("trace", []),
        "resultado": resultado,
        "meta": {
            "route": run.get("route"),
            "intent": run.get("intent"),
            "model": run.get("model"),
            "memoria": run.get("memoria", []),
        },
    }


def _resultado(run: Dict[str, Any]) -> Dict[str, Any]:
    """Mapea el resultado a una forma estructurada (tarjeta/itinerario/tabla/texto)."""
    route = run.get("route")
    intent = run.get("intent")
    final = run.get("final", "")

    if route in ("aclaracion", "confirmacion"):
        return {"tipo": "pregunta", "titulo": "NOVA pregunta", "texto": run.get("question") or final}

    if route == "nube":
        subs = (run.get("empresa") or {}).get("subtareas") or []
        if subs:
            pasos: List[dict] = []
            for i, s in enumerate(subs, 1):
                pasos.append({
                    "n": i,
                    "area": s.get("area", "-"),
                    "descripcion": s.get("descripcion", ""),
                    "finanzas": bool(s.get("requiere_finanzas")),
                    "estrategia": bool(s.get("requiere_estrategia")),
                })
            return {"tipo": "itinerario", "titulo": "Plan", "pasos": pasos, "texto": final}

    if intent == "weather":
        return {"tipo": "tarjeta", "titulo": "Clima", "cuerpo": final, "color": "mint"}

    if intent in ("set_timer", "reminder", "calendar"):
        return {"tipo": "tarjeta", "titulo": "Listo", "cuerpo": final, "color": "mint"}

    if route == "vision":
        return {"tipo": "tarjeta", "titulo": "Visión", "cuerpo": final, "color": "violet"}

    return {"tipo": "texto", "titulo": "Respuesta", "texto": final}


def _narracion(run: Dict[str, Any]) -> str:
    """Texto corto para la voz: el gist; el detalle queda en pantalla."""
    final = (run.get("final") or "").strip()
    lineas = [l for l in final.splitlines() if l.strip()]
    if not lineas:
        return ""
    if len(lineas) == 1:
        return lineas[0]
    return f"{lineas[0]} Te muestro el detalle en pantalla."
