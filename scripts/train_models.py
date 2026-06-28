"""Train the corner-time predictor from recorded session CSVs.

Pipeline:
  1. Find ``data/sessions/<track>_<car>_*.csv`` recordings.
  2. Select trainable laps with the lap-quality guardrails, optionally
     cross-checked against the lap store's track-cut (validity) flags.
  3. Extract corner-entry features (entry speed, brake point, gear, corner id)
     and the time through each corner.
  4. Train an XGBoost regressor to predict time-through-corner.
  5. Save the model to ``src/ml/models/corner_predictor_<track>_<car>.joblib``
     so :class:`src.ml.corner_predictor.TrainedCornerPredictor` can load it.

Usage::

    uv run python scripts/train_models.py --track spa --car ks_ferrari_f2004

The feature order matches ``TrainedCornerPredictor.predict``:
``[entry_speed_kmh, brake_point_pos, entry_gear, corner_index]``.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter
from pathlib import Path

# Make ``src`` importable when run directly as a script.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.config import find_ac_install, get_settings  # noqa: E402
from src.knowledge import TrackInfo, load_track  # noqa: E402
from src.ml.corner_dataset import CornerSample, build_corner_samples  # noqa: E402
from src.ml.lap_quality import LapQualityConfig, assess_laps  # noqa: E402
from src.ml.recorded_session import group_by_lap, read_samples  # noqa: E402

_FEATURE_NAMES = ("entry_speed_kmh", "brake_point_pos", "entry_gear", "corner_index")


def _session_id_from_path(path: Path, track: str, car: str) -> str:
    """Recover the session id from a ``<track>_<car>_<id>.csv`` filename."""
    return path.stem.removeprefix(f"{track}_{car}_")


def _db_invalid_csv_laps(db_path: Path, session_id: str) -> set[int]:
    """Lap store track-cut laps for a session, mapped to CSV lap indices.

    AC reports a finished lap under ``completed_laps`` *after* the crossing, so a
    DB ``lap_number = N`` corresponds to the frames recorded with CSV ``lap = N-1``.
    Best-effort: returns an empty set if the database is unavailable.
    """
    if not db_path.is_file():
        return set()
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            rows = conn.execute(
                "SELECT lap_number FROM laps WHERE session_id = ? AND valid = 0",
                (session_id,),
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return set()
    return {int(r[0]) - 1 for r in rows}


def _load_corners(track: str) -> TrackInfo:
    """Load the track's corner definitions from the local AC install."""
    settings = get_settings()
    ac_path = find_ac_install(settings.app.ac_install_path)
    if ac_path is None:
        raise SystemExit(
            "Assetto Corsa install not found. Set AC_INSTALL_PATH in .env so the "
            "trainer can read the track's corner definitions."
        )
    track_dir = Path(ac_path) / "content" / "tracks" / track
    if not track_dir.is_dir():
        raise SystemExit(f"Track folder not found: {track_dir}")
    info = load_track(track_dir, layout="")
    if not info.corners:
        raise SystemExit(
            f"Track '{track}' has no corner data (no data/sections.ini); cannot "
            "build a corner dataset."
        )
    return info


def collect_samples(
    *,
    track: str,
    car: str,
    sessions_dir: Path,
    db_path: Path,
    use_db_validity: bool,
    config: LapQualityConfig,
) -> tuple[list[CornerSample], Counter[str]]:
    """Read every session CSV and return corner samples plus a drop-reason tally."""
    info = _load_corners(track)
    csvs = sorted(sessions_dir.glob(f"{track}_{car}_*.csv"))
    if not csvs:
        raise SystemExit(f"No recordings found in {sessions_dir} for {track}/{car}.")

    rows: list[CornerSample] = []
    drop_tally: Counter[str] = Counter()
    total_laps = kept_laps = 0

    for csv_path in csvs:
        samples_by_lap = group_by_lap(read_samples(csv_path))
        invalid = (
            _db_invalid_csv_laps(db_path, _session_id_from_path(csv_path, track, car))
            if use_db_validity
            else set()
        )
        report = assess_laps(samples_by_lap, config=config, invalid_laps=invalid)
        total_laps += len(report.assessments)
        kept_laps += report.kept_count
        for dropped in report.dropped():
            for reason in dropped.reasons:
                drop_tally[reason.value] += 1
        rows.extend(build_corner_samples(samples_by_lap, info.corners, report.trainable_laps))
        print(
            f"  {csv_path.name}: {report.kept_count}/{len(report.assessments)} laps kept"
        )

    print(f"\nLaps: {kept_laps}/{total_laps} trainable across {len(csvs)} sessions")
    print(f"Corner samples: {len(rows)}")
    if drop_tally:
        summary = ", ".join(f"{k}={v}" for k, v in drop_tally.most_common())
        print(f"Dropped-lap reasons: {summary}")
    return rows, drop_tally


def train(rows: list[CornerSample], *, track: str, car: str, models_dir: Path) -> Path:
    """Train an XGBoost regressor on the corner samples and save it."""
    import joblib
    import numpy as np
    from sklearn.metrics import mean_absolute_error, r2_score
    from sklearn.model_selection import train_test_split
    from xgboost import XGBRegressor

    features = np.array(
        [
            [s.entry_speed_kmh, s.brake_point_pos, float(s.entry_gear), float(s.corner_index)]
            for s in rows
        ]
    )
    target = np.array([s.corner_time_s for s in rows])

    x_train, x_test, y_train, y_test = train_test_split(
        features, target, test_size=0.2, random_state=42
    )
    model = XGBRegressor(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        random_state=42,
    )
    model.fit(x_train, y_train)

    predicted = model.predict(x_test)
    mae = mean_absolute_error(y_test, predicted)
    r2 = r2_score(y_test, predicted)
    print(f"\nModel: MAE = {mae:.3f}s | R2 = {r2:.3f} on {len(y_test)} held-out corners")

    models_dir.mkdir(parents=True, exist_ok=True)
    out_path = models_dir / f"corner_predictor_{track}_{car}.joblib"
    joblib.dump(model, out_path)
    print(f"Saved model -> {out_path}")
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train the corner-time predictor.")
    parser.add_argument("--track", default="spa", help="Track id (folder name).")
    parser.add_argument("--car", default="ks_ferrari_f2004", help="Car model id.")
    parser.add_argument("--sessions-dir", type=Path, default=Path("data/sessions"))
    parser.add_argument("--models-dir", type=Path, default=Path("src/ml/models"))
    parser.add_argument("--min-samples", type=int, default=30)
    parser.add_argument(
        "--no-db-validity",
        action="store_true",
        help="Skip cross-checking laps against the lap store's track-cut flags.",
    )
    args = parser.parse_args(argv)

    db_path = Path(get_settings().app.database_path)
    print(f"Training corner predictor for {args.track} / {args.car}\n")
    rows, _ = collect_samples(
        track=args.track,
        car=args.car,
        sessions_dir=args.sessions_dir,
        db_path=db_path,
        use_db_validity=not args.no_db_validity,
        config=LapQualityConfig(),
    )

    if len(rows) < args.min_samples:
        print(
            f"\nNot enough data: {len(rows)} corner samples (< {args.min_samples}). "
            "Drive more clean laps and re-run."
        )
        return 1

    train(rows, track=args.track, car=args.car, models_dir=args.models_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
