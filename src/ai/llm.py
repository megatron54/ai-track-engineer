"""LLM client protocol shared by all providers.

The advisor depends only on this interface, so the local Ollama client (or any
future provider) is swappable and the advisor is testable with a fake.
"""

from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    """A minimal chat-completion interface."""

    async def complete(self, system: str, user: str) -> str:
        """Return the model's reply to a system + user message pair."""
        ...
