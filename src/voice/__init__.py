"""Voice interaction: push-to-talk questions to the race engineer.

- :mod:`src.voice.state_machine` - the pure hold-to-talk reducer (no audio,
  no asyncio; fully unit-testable).
- :mod:`src.voice.asr` / :mod:`src.voice.faster_whisper_engine` - speech-to-text.
- :mod:`src.voice.tts` / :mod:`src.voice.edge_tts_engine` - text-to-speech.

The question-answering itself reuses the existing local LLM integration (see
:meth:`~src.ai.advisor.RaceEngineerAdvisor.answer_question`) rather than a
second model - this package only adds the audio in/out layers around it.

Wiring this into the CLI (``--voice``) needs a microphone-capture library and
a global hotkey listener, both of which require real audio hardware to
validate and are left for a follow-up once this scaffold has been exercised
manually - see docs/DEEP-DIVE-ROADMAP.md, Fase 2.5.
"""

from __future__ import annotations

from src.voice.asr import AsrEngine
from src.voice.edge_tts_engine import EdgeTtsEngine
from src.voice.faster_whisper_engine import FasterWhisperEngine
from src.voice.state_machine import (
    Action,
    ButtonDown,
    ButtonUp,
    Cancel,
    DiscardRecording,
    Input,
    PipelineFailed,
    PipelineSucceeded,
    ShowState,
    StartRecording,
    StopRecordingAndRunPipeline,
    Tick,
    VoiceState,
    VoiceStateMachine,
    WarnSessionCap,
)
from src.voice.tts import TtsEngine

__all__ = [
    "Action",
    "AsrEngine",
    "ButtonDown",
    "ButtonUp",
    "Cancel",
    "DiscardRecording",
    "EdgeTtsEngine",
    "FasterWhisperEngine",
    "Input",
    "PipelineFailed",
    "PipelineSucceeded",
    "ShowState",
    "StartRecording",
    "StopRecordingAndRunPipeline",
    "Tick",
    "TtsEngine",
    "VoiceState",
    "VoiceStateMachine",
    "WarnSessionCap",
]
