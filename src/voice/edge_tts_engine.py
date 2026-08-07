"""Text-to-speech via edge-tts (free, good quality, requires network).

A thin adapter over ``edge_tts`` implementing :class:`~src.voice.tts.TtsEngine`,
using the same lazy-import pattern as :class:`~src.ai.ollama_client.OllamaClient`.
``piper-tts`` (fully offline) is the declared alternative for a fully local
setup - swap engines behind the same :class:`~src.voice.tts.TtsEngine`
protocol without touching the calling code.
"""

from __future__ import annotations

_DEFAULT_VOICE = "en-US-GuyNeural"


class EdgeTtsEngine:  # pragma: no cover - thin network adapter
    """A :class:`~src.voice.tts.TtsEngine` backed by Microsoft Edge's TTS service."""

    def __init__(self, *, voice: str = _DEFAULT_VOICE) -> None:
        self._voice = voice

    async def synthesize(self, text: str) -> bytes:
        import edge_tts

        communicate = edge_tts.Communicate(text, self._voice)
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)
