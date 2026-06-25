"""Tests for Assetto Corsa installation discovery."""

from __future__ import annotations

from pathlib import Path

from src.config import ac_paths


def _make_fake_ac_install(root: Path) -> Path:
    """Create a minimal directory tree that looks like an AC installation."""
    ac_dir = root / "steamapps" / "common" / "assettocorsa"
    (ac_dir / "content").mkdir(parents=True)
    (ac_dir / "AssettoCorsa.exe").write_text("", encoding="utf-8")
    return ac_dir


def test_find_ac_install_with_explicit_path(tmp_path: Path) -> None:
    ac_dir = _make_fake_ac_install(tmp_path)
    found = ac_paths.find_ac_install(ac_dir)
    assert found == ac_dir.resolve()


def test_find_ac_install_returns_none_when_missing(tmp_path: Path) -> None:
    # An explicit but invalid path, and no default install present.
    assert ac_paths.find_ac_install(tmp_path / "nope") is None


def test_explicit_path_is_probed_first(tmp_path: Path) -> None:
    ac_dir = _make_fake_ac_install(tmp_path)
    candidates = list(ac_paths.candidate_install_paths(ac_dir))
    assert candidates[0] == ac_dir


def test_invalid_install_missing_exe_is_rejected(tmp_path: Path) -> None:
    ac_dir = tmp_path / "steamapps" / "common" / "assettocorsa"
    (ac_dir / "content").mkdir(parents=True)
    # No AssettoCorsa.exe -> not a valid install.
    assert ac_paths.find_ac_install(ac_dir) is None
