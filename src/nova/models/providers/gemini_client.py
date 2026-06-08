"""Wrapper fino: Gemini se sirve por el cliente OpenAI-compatible (su endpoint
`/v1beta/openai/`). Se mantiene `GeminiClient` por compatibilidad de imports.
"""

from __future__ import annotations

from .openai_compatible import OpenAICompatibleClient


class GeminiClient(OpenAICompatibleClient):
    def __init__(self) -> None:
        super().__init__("gemini")
