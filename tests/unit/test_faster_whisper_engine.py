"""Tests for the pure (non-network/model) helpers behind FasterWhisperEngine."""

from __future__ import annotations

import struct
from dataclasses import dataclass

import pytest
from src.voice.faster_whisper_engine import (
    join_transcript_segments,
    pcm16_bytes_to_float32,
)


def _pcm16(*samples: int) -> bytes:
    return struct.pack(f"<{len(samples)}h", *samples)


def test_pcm16_bytes_to_float32_normalizes_full_scale_values() -> None:
    audio = pcm16_bytes_to_float32(_pcm16(0, 16384, -16384, 32767, -32768))
    assert audio[0] == pytest.approx(0.0)
    assert audio[1] == pytest.approx(0.5, abs=1e-4)
    assert audio[2] == pytest.approx(-0.5, abs=1e-4)
    assert audio[3] == pytest.approx(1.0, abs=1e-4)
    assert audio[4] == pytest.approx(-1.0, abs=1e-4)


def test_pcm16_bytes_to_float32_preserves_sample_count() -> None:
    audio = pcm16_bytes_to_float32(_pcm16(1, 2, 3, 4))
    assert len(audio) == 4


@dataclass
class _FakeSegment:
    text: str


def test_join_transcript_segments_strips_and_joins() -> None:
    segments = [_FakeSegment(" how are "), _FakeSegment("my tyres? ")]
    assert join_transcript_segments(segments) == "how are my tyres?"


def test_join_transcript_segments_handles_empty_list() -> None:
    assert join_transcript_segments([]) == ""
