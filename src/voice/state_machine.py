"""Push-to-talk voice-interaction state machine.

A pure reducer (``step(event) -> list[Action]``) for the "hold a button, ask
the engineer a question, release" interaction. The pattern is ported from
researching WhimprFlow (a Whisper dictation POC): no clock, no microphone, no
asyncio inside the machine itself - time arrives as :class:`Tick` and button
presses as :class:`ButtonDown`/:class:`ButtonUp` events, so the full
hold-to-talk / cancel / session-cap / cooldown behaviour is deterministic and
fully unit-testable without any audio hardware.

Scope (v1): push-to-talk only. WhimprFlow also has a double-tap "hands-free
lock" for long dictation sessions; a driver's question to the race engineer
is always short, so a plain hold-and-release is enough here and keeps the
machine simpler.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import assert_never

# ---- Timing (all in milliseconds, on the caller's monotonic clock) ---------

#: Ignore a press-and-release shorter than this - almost certainly a key
#: bounce or an accidental tap, not an intended question.
MIN_HOLD_MS = 150
#: Hard cap on a single recording. A driver's question should never need this
#: long; this protects against a stuck key/button recording indefinitely.
SESSION_CAP_MS = 15_000
#: Warn once the recording approaches the cap, so the UI can nudge the driver.
WARN_AT_MS = 12_000
#: Minimum gap between finishing one session and starting the next - avoids a
#: rapid double-trigger from key-repeat or a sticky button.
COOLDOWN_MS = 300


class VoiceState(Enum):
    """The machine's current phase."""

    IDLE = auto()
    RECORDING = auto()
    FINALIZING = auto()


# ---- Inputs -----------------------------------------------------------------


@dataclass(frozen=True)
class ButtonDown:
    """The push-to-talk button/key was pressed."""

    at_ms: int


@dataclass(frozen=True)
class ButtonUp:
    """The push-to-talk button/key was released."""

    at_ms: int


@dataclass(frozen=True)
class Cancel:
    """An explicit cancel (e.g. an Escape key) during recording or finalizing."""

    at_ms: int


@dataclass(frozen=True)
class PipelineSucceeded:
    """The transcribe -> ask -> speak pipeline finished for the active session."""

    at_ms: int


@dataclass(frozen=True)
class PipelineFailed:
    """The pipeline errored (ASR/LLM/TTS failure) for the active session."""

    at_ms: int


@dataclass(frozen=True)
class Tick:
    """A clock tick, for session-cap warnings and auto-stop."""

    now_ms: int


Input = ButtonDown | ButtonUp | Cancel | PipelineSucceeded | PipelineFailed | Tick


# ---- Actions (side effects for the caller to perform) ----------------------


@dataclass(frozen=True)
class StartRecording:
    """Begin capturing microphone audio for ``session``."""

    session: int


@dataclass(frozen=True)
class StopRecordingAndRunPipeline:
    """Stop capturing and run transcribe -> ask -> speak for ``session``."""

    session: int


@dataclass(frozen=True)
class DiscardRecording:
    """Stop capturing and discard ``session`` without running the pipeline."""

    session: int


@dataclass(frozen=True)
class ShowState:
    """The UI should reflect the machine's new state."""

    state: VoiceState


@dataclass(frozen=True)
class WarnSessionCap:
    """The active recording is approaching :data:`SESSION_CAP_MS`."""


Action = (
    StartRecording
    | StopRecordingAndRunPipeline
    | DiscardRecording
    | ShowState
    | WarnSessionCap
)


class VoiceStateMachine:
    """Push-to-talk state machine for the voice race-engineer assistant."""

    def __init__(self) -> None:
        self._state = VoiceState.IDLE
        self._next_session = 1
        self._session: int | None = None
        self._started_ms = 0
        self._warned = False
        self._last_end_ms: int | None = None

    @property
    def state(self) -> VoiceState:
        return self._state

    def step(self, event: Input) -> list[Action]:
        """Advance the machine by one event, returning the actions to perform."""
        match event:
            case ButtonDown(at_ms=at_ms):
                return self._on_button_down(at_ms)
            case ButtonUp(at_ms=at_ms):
                return self._on_button_up(at_ms)
            case Cancel(at_ms=at_ms):
                return self._on_cancel(at_ms)
            case PipelineSucceeded(at_ms=at_ms) | PipelineFailed(at_ms=at_ms):
                return self._on_pipeline_done(at_ms)
            case Tick(now_ms=now_ms):
                return self._on_tick(now_ms)
            case _:  # pragma: no cover - Input is a closed union; defence in depth
                assert_never(event)

    def _in_cooldown(self, now_ms: int) -> bool:
        return self._last_end_ms is not None and now_ms - self._last_end_ms < COOLDOWN_MS

    def _on_button_down(self, at_ms: int) -> list[Action]:
        if self._state is not VoiceState.IDLE or self._in_cooldown(at_ms):
            return []
        session = self._next_session
        self._next_session += 1
        self._session = session
        self._started_ms = at_ms
        self._warned = False
        self._state = VoiceState.RECORDING
        return [StartRecording(session=session), ShowState(state=self._state)]

    def _on_button_up(self, at_ms: int) -> list[Action]:
        if self._state is not VoiceState.RECORDING:
            return []
        held = at_ms - self._started_ms
        if held < MIN_HOLD_MS:
            return self._discard(at_ms)
        return self._finalize(at_ms)

    def _on_cancel(self, at_ms: int) -> list[Action]:
        if self._state in (VoiceState.RECORDING, VoiceState.FINALIZING):
            return self._discard(at_ms)
        return []

    def _on_pipeline_done(self, at_ms: int) -> list[Action]:
        if self._state is not VoiceState.FINALIZING:
            return []
        self._state = VoiceState.IDLE
        self._session = None
        # Cooldown is measured from when the pipeline actually finished (the
        # driver could plausibly hear the reply and reach for the button
        # again), not from when recording stopped - a slow ASR/LLM/TTS call
        # would otherwise leave the cooldown with no effect at all.
        self._last_end_ms = at_ms
        return [ShowState(state=self._state)]

    def _on_tick(self, now_ms: int) -> list[Action]:
        if self._state is not VoiceState.RECORDING:
            return []
        elapsed = now_ms - self._started_ms
        if elapsed >= SESSION_CAP_MS:
            return self._finalize(now_ms)
        if elapsed >= WARN_AT_MS and not self._warned:
            self._warned = True
            return [WarnSessionCap()]
        return []

    def _finalize(self, at_ms: int) -> list[Action]:
        assert self._session is not None
        session = self._session
        self._state = VoiceState.FINALIZING
        # Not setting _last_end_ms here: the cooldown should measure from
        # when the pipeline actually finishes (_on_pipeline_done), which is
        # the only moment a new ButtonDown could legally arrive (the machine
        # rejects ButtonDown while not IDLE). Setting it here too would just
        # be immediately superseded and invites confusion about which value
        # is authoritative.
        return [
            StopRecordingAndRunPipeline(session=session),
            ShowState(state=self._state),
        ]

    def _discard(self, at_ms: int) -> list[Action]:
        assert self._session is not None
        session = self._session
        self._state = VoiceState.IDLE
        self._session = None
        self._last_end_ms = at_ms
        return [DiscardRecording(session=session), ShowState(state=self._state)]
