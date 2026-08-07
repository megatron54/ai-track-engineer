"""Tests for the push-to-talk voice state machine."""

from __future__ import annotations

from src.voice.state_machine import (
    COOLDOWN_MS,
    MIN_HOLD_MS,
    SESSION_CAP_MS,
    WARN_AT_MS,
    ButtonDown,
    ButtonUp,
    Cancel,
    DiscardRecording,
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


def test_hold_and_release_starts_and_finalizes() -> None:
    machine = VoiceStateMachine()
    actions = machine.step(ButtonDown(at_ms=0))
    assert any(isinstance(a, StartRecording) for a in actions)
    assert machine.state is VoiceState.RECORDING

    actions = machine.step(ButtonUp(at_ms=MIN_HOLD_MS + 50))
    assert any(isinstance(a, StopRecordingAndRunPipeline) for a in actions)
    assert machine.state is VoiceState.FINALIZING


def test_short_tap_is_discarded_not_finalized() -> None:
    machine = VoiceStateMachine()
    machine.step(ButtonDown(at_ms=0))
    actions = machine.step(ButtonUp(at_ms=MIN_HOLD_MS - 10))
    assert any(isinstance(a, DiscardRecording) for a in actions)
    assert not any(isinstance(a, StopRecordingAndRunPipeline) for a in actions)
    assert machine.state is VoiceState.IDLE


def test_pipeline_success_returns_to_idle() -> None:
    machine = VoiceStateMachine()
    machine.step(ButtonDown(at_ms=0))
    machine.step(ButtonUp(at_ms=500))
    assert machine.state is VoiceState.FINALIZING
    actions = machine.step(PipelineSucceeded(at_ms=2500))
    assert machine.state is VoiceState.IDLE
    assert any(isinstance(a, ShowState) and a.state is VoiceState.IDLE for a in actions)


def test_pipeline_failure_also_returns_to_idle() -> None:
    machine = VoiceStateMachine()
    machine.step(ButtonDown(at_ms=0))
    machine.step(ButtonUp(at_ms=500))
    machine.step(PipelineFailed(at_ms=2500))
    assert machine.state is VoiceState.IDLE


def test_button_down_ignored_while_recording() -> None:
    machine = VoiceStateMachine()
    machine.step(ButtonDown(at_ms=0))
    actions = machine.step(ButtonDown(at_ms=100))
    assert actions == []
    assert machine.state is VoiceState.RECORDING


def test_cancel_during_recording_discards() -> None:
    machine = VoiceStateMachine()
    machine.step(ButtonDown(at_ms=0))
    actions = machine.step(Cancel(at_ms=200))
    assert any(isinstance(a, DiscardRecording) for a in actions)
    assert machine.state is VoiceState.IDLE


def test_cancel_when_idle_is_a_no_op() -> None:
    machine = VoiceStateMachine()
    assert machine.step(Cancel(at_ms=0)) == []


def test_cooldown_suppresses_immediate_retrigger() -> None:
    machine = VoiceStateMachine()
    machine.step(ButtonDown(at_ms=0))
    machine.step(Cancel(at_ms=100))  # sets last_end_ms = 100
    assert machine.step(ButtonDown(at_ms=100 + COOLDOWN_MS - 1)) == []
    assert machine.step(ButtonDown(at_ms=100 + COOLDOWN_MS + 1)) != []


def test_cooldown_measures_from_pipeline_completion_not_recording_stop() -> None:
    # A slow ASR/LLM/TTS call must not leave the cooldown toothless: the
    # clock starts when the pipeline actually finishes, not when the button
    # was released (which is when FINALIZING begins).
    machine = VoiceStateMachine()
    machine.step(ButtonDown(at_ms=0))
    machine.step(ButtonUp(at_ms=500))  # -> FINALIZING
    machine.step(PipelineSucceeded(at_ms=3_000))  # pipeline took 2.5s -> IDLE

    # Immediately after completion (well past the old recording-stop time,
    # but within COOLDOWN_MS of the actual completion) a retrigger is
    # suppressed.
    assert machine.step(ButtonDown(at_ms=3_000 + COOLDOWN_MS - 1)) == []
    assert machine.step(ButtonDown(at_ms=3_000 + COOLDOWN_MS + 1)) != []


def test_session_cap_warns_then_auto_finalizes() -> None:
    machine = VoiceStateMachine()
    machine.step(ButtonDown(at_ms=0))
    actions = machine.step(Tick(now_ms=WARN_AT_MS))
    assert any(isinstance(a, WarnSessionCap) for a in actions)
    # The warning only fires once.
    actions = machine.step(Tick(now_ms=WARN_AT_MS + 1))
    assert not any(isinstance(a, WarnSessionCap) for a in actions)
    actions = machine.step(Tick(now_ms=SESSION_CAP_MS))
    assert any(isinstance(a, StopRecordingAndRunPipeline) for a in actions)
    assert machine.state is VoiceState.FINALIZING


def test_tick_is_a_no_op_when_idle() -> None:
    machine = VoiceStateMachine()
    assert machine.step(Tick(now_ms=1000)) == []


def test_button_up_ignored_when_idle() -> None:
    machine = VoiceStateMachine()
    assert machine.step(ButtonUp(at_ms=0)) == []


def test_sessions_get_distinct_ids() -> None:
    machine = VoiceStateMachine()
    first = machine.step(ButtonDown(at_ms=0))
    machine.step(ButtonUp(at_ms=500))
    machine.step(PipelineSucceeded(at_ms=600))

    second = machine.step(ButtonDown(at_ms=600 + COOLDOWN_MS + 1))
    first_start = next(a for a in first if isinstance(a, StartRecording))
    second_start = next(a for a in second if isinstance(a, StartRecording))
    assert first_start.session != second_start.session


def test_stray_pipeline_event_while_idle_is_a_no_op() -> None:
    # A late/duplicate pipeline event arriving after the machine already
    # returned to idle (e.g. a race between a cancel and a slow ASR call)
    # must not be acted on.
    machine = VoiceStateMachine()
    assert machine.step(PipelineSucceeded(at_ms=0)) == []
    assert machine.step(PipelineFailed(at_ms=0)) == []
    assert machine.state is VoiceState.IDLE


def test_cancel_during_finalizing_discards_and_returns_to_idle() -> None:
    machine = VoiceStateMachine()
    machine.step(ButtonDown(at_ms=0))
    machine.step(ButtonUp(at_ms=500))
    assert machine.state is VoiceState.FINALIZING
    actions = machine.step(Cancel(at_ms=600))
    assert any(isinstance(a, DiscardRecording) for a in actions)
    assert machine.state is VoiceState.IDLE


def test_button_up_ignored_while_finalizing() -> None:
    machine = VoiceStateMachine()
    machine.step(ButtonDown(at_ms=0))
    machine.step(ButtonUp(at_ms=500))
    assert machine.state is VoiceState.FINALIZING
    assert machine.step(ButtonUp(at_ms=600)) == []
    assert machine.state is VoiceState.FINALIZING
