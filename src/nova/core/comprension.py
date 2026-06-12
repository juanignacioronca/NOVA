"""Motor de comprensión del Conductor.

`comprender(texto, images, contexto) -> Intent`. Orden de decisión:

1. **Determinístico** (`clasificar_rapido`): saludos/charla trivial y pedidos
   claros de herramienta (hora, clima, timer, recordatorio, calendario) se
   clasifican por reglas, sin llamar a ningún modelo → instantáneo y confiable
   (los modelos chicos alucinan justo en estos casos).
2. **Modelo** (JSON estricto, temperatura baja + few-shot): para todo lo demás.
   Parseo tolerante; reintenta una vez "solo JSON".
3. **Heurística** por palabras clave: respaldo si no hay modelo (stub) o el
   JSON falla.

Soporta imágenes (multimodal): arma mensajes en formato visión OpenAI-compatible
y enruta a `conductor_vision`.

Seguridad: las instrucciones de NOVA van SOLO en `system`; el texto del usuario
viaja en `user` como DATO. Se detecta (no se obedece) cualquier intento de
override y se marca en el `Intent`. Ver CLAUDE.md §11.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..models import model_router
from . import prompts
from .security import detectar_inyeccion

UMBRAL_CONFIANZA = 0.5

# Opciones de muestreo para clasificar: determinista y corto (clave con modelos
# chicos locales; con el default del proveedor (~0.8) la clasificación es ruido).
_OPTS_CLASIFICACION = {
    "temperature": 0.1,
    "max_tokens": 300,
    "response_format": {"type": "json_object"},
}


def __getattr__(name: str):
    """Compat: `COMPREHENSION_SYSTEM` ahora vive en `core.prompts` (editable)."""
    if name == "COMPREHENSION_SYSTEM":
        return prompts.get("comprension")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


@dataclass
class Intent:
    intencion: str = "general"
    entidades: Dict[str, Any] = field(default_factory=dict)
    faltantes: List[str] = field(default_factory=list)
    complejidad: str = "simple"  # "simple" | "complejo"
    confianza: float = 0.5
    multimodal: bool = False
    inyeccion_detectada: bool = False
    fuente: str = "heuristica"  # "determinista" | "modelo" | "heuristica" | spec del proveedor

    def necesita_aclaracion(self, umbral: float = UMBRAL_CONFIANZA) -> bool:
        return bool(self.faltantes) or self.confianza < umbral


# --- normalización ---
def _norm(texto: str) -> str:
    decomposed = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


# --- charla trivial (saludos, gracias, ok): respuesta local instantánea ---
_SMALLTALK_FRASES = {
    "hola", "buenas", "hey", "hi", "hello", "holis", "holaa", "buen dia",
    "buenos dias", "buenas tardes", "buenas noches", "como estas", "como andas",
    "como va", "como va todo", "que tal", "todo bien", "que haces", "que contas",
    "gracias", "muchas gracias", "mil gracias", "genial", "perfecto", "joya",
    "dale", "ok", "okey", "listo", "barbaro", "buenisimo", "chau", "adios",
    "hasta luego", "hasta manana", "nos vemos", "saludos", "estas ahi",
    "me escuchas", "probando", "test",
}
_SMALLTALK_WORDS = {
    w for frase in _SMALLTALK_FRASES for w in frase.split()
} | {"nova", "che", "igualmente", "vos", "bien", "muy"}
_FILLER_WORDS = {"nova", "che", "porfa", "por", "favor", "eh", "em", "y", "bueno"}


def es_smalltalk(texto: str) -> bool:
    """True si el mensaje es SOLO saludo/charla trivial (sin pedido adentro)."""
    limpio = re.sub(r"[^a-z0-9 ]+", " ", _norm(texto)).strip()
    limpio = re.sub(r"\s+", " ", limpio)
    if not limpio:
        return False
    if limpio in _SMALLTALK_FRASES:
        return True
    toks = [t for t in limpio.split() if t not in _FILLER_WORDS]
    if not toks:
        return True  # solo "nova", "che", etc.
    return len(toks) <= 5 and all(t in _SMALLTALK_WORDS for t in toks)


# --- heurística (respaldo sin modelo) ---
_COMPLEX_KW = (
    "organiz", "planif", "plane", "research", "investig", "compar",
    "estrateg", "finde", "viaje", "itinerario", "presupuesto", "analiz",
)
_SIMPLE_KW = (
    "timer", "temporizador", "alarma", "clima", "tiempo", "weather",
    "calendario", "agenda", "hora", "recordar", "recordatorio",
    "recuerda", "recorda", "remind", "lista de compras", "lista del super",
)
_INTENT_MAP = (
    (("lista de compras", "lista del super", "lista de la compra", "que hay que comprar", "que tengo que comprar"), "shopping"),
    (("timer", "temporizador", "alarma"), "set_timer"),
    (("clima", "weather", "tiempo"), "weather"),
    (("recordar", "recordatorio", "recuerda", "recorda", "remind"), "reminder"),
    (("calendario", "agenda", "hora"), "calendar"),
    (("organiz", "planif", "plane"), "plan"),
    (("research", "investig"), "research"),
    (("compar", "analiz", "estrateg", "viaje", "itinerario", "presupuesto"), "strategy"),
)
# Pedidos claros de herramienta → clasificación determinística (sin modelo).
_TOOL_INTENT_MAP = (
    (("que hora", "la hora", "hora es", "que dia es", "que fecha", "fecha de hoy", "dia de hoy"), "hora"),
    (("timer", "temporizador", "alarma"), "set_timer"),
    (("clima", "temperatura", "pronostico", "va a llover", "lluvia", "tiempo hace", "que tiempo"), "weather"),
    (("recordame", "recordatorio", "recuerdame", "acordame", "recordar", "recorda", "recuerda", "remind"), "reminder"),
    (("mi calendario", "mi agenda", "que tengo agendado", "mis eventos", "que tengo hoy"), "calendar"),
    (("no podes hacer", "no sabes hacer", "que te falta", "que no sabes"), "pendientes"),
)
_DURATION_RE = re.compile(r"(\d+)\s*(horas?|minutos?|min|m|segundos?|seg|s)\b")
_WHEN_RE = re.compile(
    r"\b(hoy|manana|pasado manana|esta noche|este finde|este fin de semana|"
    r"proxim[oa]|que viene|semana que viene|lunes|martes|miercoles|jueves|"
    r"viernes|sabado|domingo|\d{1,2}[/-]\d{1,2})\b"
)
_WHO_RE = re.compile(
    r"\b(solo|sola|con mi |con mis |con la |con el |con un |con una |con amig|"
    r"en familia|mi pareja|mi novi|mi herman|mi famili|mis amig)"
)


def _extraer_entidades(norm: str) -> Dict[str, Any]:
    entidades: Dict[str, Any] = {}
    dur = _DURATION_RE.search(norm)
    if dur:
        entidades["duracion"] = dur.group(1)
        entidades["unidad"] = dur.group(2)
    if _WHEN_RE.search(norm):
        entidades["cuando"] = _WHEN_RE.search(norm).group(0)
    if _WHO_RE.search(norm):
        entidades["con_quien"] = _WHO_RE.search(norm).group(0).strip()
    return entidades


def _faltantes(intencion: str, complejidad: str, norm: str, entidades: Dict[str, Any]) -> List[str]:
    """Solo para planes personales (intent 'plan'): si faltan fecha/compañía, pregunta."""
    if complejidad != "complejo" or intencion != "plan":
        return []
    faltan: List[str] = []
    if "cuando" not in entidades:
        es_finde = "finde" in norm or "fin de semana" in norm
        faltan.append("qué fin de semana" if es_finde else "qué fecha")
    if "con_quien" not in entidades:
        faltan.append("con quién")
    return faltan


def clasificar_rapido(texto: str) -> Optional[Intent]:
    """Clasificación determinística para lo trivial: charla y pedidos claros de
    herramienta. Devuelve None si el mensaje amerita modelo/heurística."""
    if es_smalltalk(texto):
        return Intent(
            intencion="charla", complejidad="simple", confianza=0.95,
            inyeccion_detectada=detectar_inyeccion(texto), fuente="determinista",
        )
    norm = _norm(texto)
    # Pedidos de una palabra ("hora", "fecha") — típico de STT recortado.
    if norm.strip(" .!?¿¡") in ("hora", "la hora", "fecha", "la fecha"):
        return Intent(
            intencion="hora", complejidad="simple", confianza=0.9,
            inyeccion_detectada=detectar_inyeccion(texto), fuente="determinista",
        )
    # Con señales de tarea compleja (o un texto largo) decide el modelo.
    if any(k in norm for k in _COMPLEX_KW) or len(norm.split()) > 14:
        return None
    for keys, label in _TOOL_INTENT_MAP:
        if any(k in norm for k in keys):
            return Intent(
                intencion=label, entidades=_extraer_entidades(norm),
                complejidad="simple", confianza=0.9,
                inyeccion_detectada=detectar_inyeccion(texto), fuente="determinista",
            )
    return None


def heuristica(texto: str, multimodal: bool = False) -> Intent:
    """Comprensión por palabras clave (sin modelo)."""
    norm = _norm(texto)
    if es_smalltalk(texto):
        return Intent(
            intencion="charla", complejidad="simple", confianza=0.9,
            multimodal=multimodal, inyeccion_detectada=detectar_inyeccion(texto),
            fuente="heuristica",
        )
    complejidad = "complejo" if any(k in norm for k in _COMPLEX_KW) else "simple"
    intencion = "general"
    for keys, label in _INTENT_MAP:
        if any(k in norm for k in keys):
            intencion = label
            break
    entidades = _extraer_entidades(norm)
    faltan = _faltantes(intencion, complejidad, norm, entidades)
    if faltan:
        confianza = 0.4
    elif intencion == "general":
        confianza = 0.55
    else:
        confianza = 0.8
    return Intent(
        intencion=intencion,
        entidades=entidades,
        faltantes=faltan,
        complejidad=complejidad,
        confianza=confianza,
        multimodal=multimodal,
        inyeccion_detectada=detectar_inyeccion(texto),
        fuente="heuristica",
    )


# --- imágenes (multimodal paso 1) ---
def cargar_imagen(path: str) -> str:
    """Lee una imagen y la devuelve como data URL base64 (formato visión)."""
    with open(path, "rb") as fh:
        data = fh.read()
    mime = mimetypes.guess_type(path)[0] or "image/png"
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def mensajes_vision(sistema: str, texto: str, image_paths: List[str]) -> List[dict]:
    """Mensajes en formato visión OpenAI-compatible (texto + image_url)."""
    content: List[dict] = [{"type": "text", "text": texto}]
    for path in image_paths:
        content.append({"type": "image_url", "image_url": {"url": cargar_imagen(path)}})
    return [{"role": "system", "content": sistema}, {"role": "user", "content": content}]


# --- parseo tolerante de JSON ---
def _extraer_json(texto: str) -> Optional[dict]:
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio == -1 or fin == -1 or fin <= inicio:
        return None
    try:
        data = json.loads(texto[inicio : fin + 1])
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


def _intent_de_json(data: dict, texto: str, multimodal: bool, fuente: str) -> Intent:
    complejidad = data.get("complejidad", "simple")
    if complejidad not in ("simple", "complejo"):
        complejidad = "complejo" if complejidad else "simple"
    try:
        confianza = float(data.get("confianza", 0.6))
    except (TypeError, ValueError):
        confianza = 0.6
    faltantes = data.get("faltantes") or []
    if not isinstance(faltantes, list):
        faltantes = [str(faltantes)]
    entidades = data.get("entidades") or {}
    if not isinstance(entidades, dict):
        entidades = {}
    return Intent(
        intencion=str(data.get("intencion", "general")),
        entidades=entidades,
        faltantes=[str(f) for f in faltantes],
        complejidad=complejidad,
        confianza=max(0.0, min(1.0, confianza)),
        multimodal=multimodal,
        inyeccion_detectada=detectar_inyeccion(texto),
        fuente=fuente,
    )


def _looks_stub(texto: str) -> bool:
    return texto.lstrip().startswith("[stub:")


def _bloque_usuario(texto: str, contexto: Optional[dict]) -> str:
    """Texto del usuario como DATO (en rol user, nunca system)."""
    if not contexto:
        return texto
    return f"{texto}\n\n[contexto previo: {json.dumps(contexto, ensure_ascii=False)}]"


# --- punto de entrada ---
async def comprender(
    texto: str,
    images: Optional[List[str]] = None,
    contexto: Optional[dict] = None,
) -> Intent:
    """Entiende el pedido. Primero reglas deterministas (charla/herramientas);
    con imágenes usa `conductor_vision`; si el modelo no da JSON válido o es
    stub, cae a heurística (sigue corriendo sin modelos)."""
    images = images or []
    multimodal = bool(images)

    # 0) Lo trivial no gasta modelo: saludo / pedido claro de herramienta.
    if not multimodal:
        rapido = clasificar_rapido(texto)
        if rapido is not None:
            return rapido

    # 1) Armar mensajes y elegir modelo (sin mezclar contenido en system).
    sistema = prompts.get("comprension")
    if multimodal:
        modelo_key = "conductor_vision"
        messages = mensajes_vision(sistema, _bloque_usuario(texto, contexto), images)
    else:
        modelo_key = "conductor_simple"
        messages = [
            {"role": "system", "content": sistema},
            {"role": "user", "content": _bloque_usuario(texto, contexto)},
        ]

    # 2) Llamar al modelo (muestreo determinista, salida JSON).
    comp = await model_router.complete_meta(modelo_key, messages, **_OPTS_CLASIFICACION)
    if _looks_stub(comp.text):
        return heuristica(texto, multimodal=multimodal)

    data = _extraer_json(comp.text)
    if data is None:
        # 3) Reintento: pedir SOLO JSON.
        retry = list(messages) + [
            {"role": "user", "content": "Devolvé ÚNICAMENTE el JSON pedido, sin nada más."}
        ]
        comp2 = await model_router.complete_meta(modelo_key, retry, **_OPTS_CLASIFICACION)
        data = None if _looks_stub(comp2.text) else _extraer_json(comp2.text)
        if data is None:
            return heuristica(texto, multimodal=multimodal)
        comp = comp2

    # Nota: antes acá se escalaba a la nube (conductor_complex) ante baja confianza.
    # Se quitó: agregaba latencia de red en casi toda charla casual y lo simple ahora
    # lo responde el Conductor directo. La clasificación local alcanza para rutear.
    return _intent_de_json(data, texto, multimodal, comp.spec)
