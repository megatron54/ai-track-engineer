"""Local LLM client backed by Ollama.

A thin adapter over the ``ollama`` async client implementing :class:`LLMClient`.
Network calls are exercised against a real Ollama server (integration), so they
are excluded from unit coverage; the advisor is unit-tested with a fake client.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config.settings import OllamaSettings


class OllamaClient:  # pragma: no cover - thin network adapter
    """An :class:`~src.ai.llm.LLMClient` backed by a local Ollama server."""

    def __init__(self, *, url: str, model: str) -> None:
        from ollama import AsyncClient

        self._model = model
        self._client = AsyncClient(host=url)

    @classmethod
    def from_settings(cls, settings: OllamaSettings) -> OllamaClient:
        return cls(url=settings.url, model=settings.model)

    async def complete(self, system: str, user: str) -> str:
        response = await self._client.chat(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return str(response["message"]["content"])

    async def is_available(self) -> bool:
        """Whether the Ollama server is reachable."""
        try:
            await self._client.list()
        except Exception:
            return False
        return True
