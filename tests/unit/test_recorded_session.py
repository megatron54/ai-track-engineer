"""Tests for reading recorded-session CSVs into ML samples."""

from __future__ import annotations

from pathlib import Path

from src.ml.recorded_session import TelemetrySample, group_by_lap, read_samples

_HEADER = (
    "timestamp,lap,lap_pos,speed_kmh,gear,brake,g_lat,"
    "tyre_temp_fl,tyre_temp_fr,tyre_temp_rl,tyre_temp_rr"
)


def _write_csv(path: Path, rows: list[tuple[object, ...]]) -> None:
    lines = [_HEADER]
    lines.extend(",".join(str(value) for value in row) for row in rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_read_samples_parses_channels(tmp_path: Path) -> None:
    csv_path = tmp_path / "session.csv"
    _write_csv(
        csv_path,
        [
            (1.00, 0, 0.10, 120.0, 3, 0.0, 0.2, 80, 82, 84, 86),
            (1.05, 1, 0.50, 250.0, 6, 0.1, 1.5, 90, 92, 94, 96),
        ],
    )
    samples = read_samples(csv_path)
    assert len(samples) == 2
    assert samples[0].lap == 0
    assert samples[1].lap == 1
    assert samples[1].speed_kmh == 250.0
    assert samples[1].gear == 6
    assert samples[0].tyre_temp_avg == (80 + 82 + 84 + 86) / 4


def test_read_samples_returns_immutable_samples(tmp_path: Path) -> None:
    csv_path = tmp_path / "session.csv"
    _write_csv(csv_path, [(1.0, 1, 0.5, 200.0, 4, 0.0, 0.0, 90, 90, 90, 90)])
    sample = read_samples(csv_path)[0]
    assert isinstance(sample, TelemetrySample)


def test_group_by_lap_preserves_order(tmp_path: Path) -> None:
    csv_path = tmp_path / "session.csv"
    _write_csv(
        csv_path,
        [
            (1.0, 0, 0.10, 100, 3, 0, 0, 80, 80, 80, 80),
            (1.1, 1, 0.20, 100, 4, 0, 0, 90, 90, 90, 90),
            (1.2, 1, 0.30, 100, 4, 0, 0, 90, 90, 90, 90),
            (1.3, 2, 0.10, 100, 4, 0, 0, 90, 90, 90, 90),
        ],
    )
    grouped = group_by_lap(read_samples(csv_path))
    assert set(grouped) == {0, 1, 2}
    assert len(grouped[1]) == 2
    assert [s.lap_pos for s in grouped[1]] == [0.20, 0.30]


def test_group_by_lap_empty() -> None:
    assert group_by_lap([]) == {}
