"""Tests for the CLI and structured logging."""

from __future__ import annotations

from src import __version__
from src.main import app
from src.observability import get_logger
from src.observability import logging as logging_module
from typer.testing import CliRunner

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_doctor_command_runs() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0


def test_run_command_mock_mode() -> None:
    result = runner.invoke(app, ["run", "--mock"])
    assert result.exit_code == 0
    assert "mock" in result.stdout.lower()


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    # no_args_is_help renders the help screen and exits with Click's usage code.
    assert result.exit_code == 2
    assert "Usage" in result.output or "Commands" in result.output


def test_logging_configures_and_returns_logger() -> None:
    logging_module._configured = False
    log = get_logger("test")
    assert log is not None
    assert logging_module._configured is True


def test_logging_invalid_level_defaults_to_info() -> None:
    logging_module.configure_logging("NOT_A_LEVEL")
    assert logging_module._configured is True
