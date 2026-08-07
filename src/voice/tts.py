"""Text-to-speech engine protocol shared by all providers.

Mirrors :mod:`src.voice.asr`: a pure output-layer interface so the engineer's
already-generated text response (from :class:`~src.ai.advisor.RaceEngineerAdvisor`)
can be spoken without the rest of the voice pipeline caring which TTS backend
is behind it.
"""

from __future__ import annotations

from typing import Protocol


class TtsEngine(Protocol):
    """A minimal text-to-speech interface: text in, playable audio bytes out."""

    async def synthesize(self, text: str) -> bytes:
        """Render ``text`` to audio bytes (encoding is engine-specific, e.g. MP3/WAV)."""
        ...
