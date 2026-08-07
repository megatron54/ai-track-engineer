"""Speech-to-text engine protocol shared by all providers.

Mirrors :mod:`src.ai.llm`: the voice pipeline depends only on this interface,
so a fake is trivial to test with and a real engine (faster-whisper) is
swappable behind it without touching the pipeline logic.
"""

from __future__ import annotations

from typing import Protocol


class AsrEngine(Protocol):
    """A minimal speech-to-text interface: mono 16 kHz PCM16 bytes in, text out."""

    async def transcribe(self, pcm16k: bytes) -> str:
        """Transcribe one short utterance (already resampled to 16 kHz mono PCM16).

        Implementations should treat the input as a single, self-contained
        clip (a push-to-talk question), not a stream to be transcribed
        incrementally.
        """
        ...
