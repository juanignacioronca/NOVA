"""Clientes de proveedores de modelos.

- `ollama_client`     — local ($0), OpenAI-ish vía API nativa de Ollama.
- `openai_compatible` — Groq, OpenRouter y DeepSeek (misma interfaz, cambia
  base_url + key).
- `gemini_client`     — Gemini (API nativa generateContent).

Todos exponen la misma interfaz `Provider` (ver `base.py`).
"""
