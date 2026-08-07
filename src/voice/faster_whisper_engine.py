"""Local speech-to-text via faster-whisper.

A thin adapter over ``faster_whisper.WhisperModel`` implementing
:class:`~src.voice.asr.AsrEngine`, following the same lazy-import pattern as
:class:`~src.ai.ollama_client.OllamaClient` so the module can be imported
without the (heavy, optional) ``voice`` extra installed.

Tuned for short push-to-talk utterances, not long-form transcription:
``condition_on_previous_text=False`` stops the model dragging in context from
a previous, unrelated question (the same repetition failure mode WhimprFlow
documents for whisper.cpp on short clips), and ``vad_filter=True`` trims the
silence padding a push-to-talk clip typically has at both ends.
"""

from __future__ import annotations

import asyncio

import numpy as np

_SAMPLE_RATE_HZ = 16_000
_PCM16_MAX = 32768.0


def pcm16_bytes_to_float32(pcm16k: bytes) -> np.ndarray:
    """Convert little-endian mono PCM16 bytes to a float32 array in [-1, 1].

    Pulled out of :class:`FasterWhisperEngine` so this normalisation - the
    one piece of real, non-I/O logic in the adapter - is directly unit
    tested without needing the (heavy, optional) faster-whisper model.
    """
    return np.frombuffer(pcm16k, dtype=np.int16).astype(np.float32) / _PCM16_MAX


def join_transcript_segments(segments: object) -> str:
    """Join faster-whisper's per-segment text into one trimmed transcript."""
    return " ".join(segment.text.strip() for segment in segments).strip()  # type: ignore[attr-defined]


class FasterWhisperEngine:  # pragma: no cover - thin model adapter, no network/model in CI
    """An :class:`~src.voice.asr.AsrEngine` backed by a local faster-whisper model."""

    def __init__(self, *, model_size: str = "base.en", device: str = "cpu") -> None:
        from faster_whisper import WhisperModel

        self._model = WhisperModel(model_size, device=device)

    async def transcribe(self, pcm16k: bytes) -> str:
        # faster-whisper's transcribe() is a blocking, CPU-bound call; run it
        # off the event loop so it doesn't stall telemetry processing.
        return await asyncio.to_thread(self._transcribe_sync, pcm16k)

    def _transcribe_sync(self, pcm16k: bytes) -> str:
        audio = pcm16_bytes_to_float32(pcm16k)
        segments, _ = self._model.transcribe(
            audio,
            language="en",
            condition_on_previous_text=False,
            vad_filter=True,
        )
        return join_transcript_segments(segments)
