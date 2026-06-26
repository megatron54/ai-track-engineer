"""Tests for ML feature engineering and corner predictor."""

from __future__ import annotations

from src.ml import HeuristicCornerPredictor, corner_entry_features, frame_features

from tests.factories import make_frame


def test_frame_features_shape() -> None:
    features = frame_features(make_frame(speed_kmh=200.0, rpm=8000, gear=5))
    assert features["speed_kmh"] == 200.0
    assert features["rpm"] == 8000
    assert features["gear"] == 5
    assert "tyre_temp_avg" in features
    assert "lap_pos" in features
    assert len(features) >= 15


def test_corner_entry_features() -> None:
    features = corner_entry_features(speed_kmh=150.0, brake_point_pos=0.42, gear=4, g_lat=1.2)
    assert features["entry_speed_kmh"] == 150.0
    assert features["brake_point_pos"] == 0.42


def test_heuristic_predictor_is_not_trained() -> None:
    pred = HeuristicCornerPredictor()
    assert pred.is_trained() is False


def test_heuristic_prediction_returns_positive_time() -> None:
    pred = HeuristicCornerPredictor(avg_corner_time_s=5.0)
    result = pred.predict(corner_index=3, entry_speed=150.0, brake_point=0.4, gear=4)
    assert result.predicted_time_s > 0
    assert result.confidence < 0.5
    assert result.corner_index == 3


def test_faster_entry_reduces_predicted_time() -> None:
    pred = HeuristicCornerPredictor()
    slow = pred.predict(corner_index=1, entry_speed=80.0, brake_point=0.4, gear=3)
    fast = pred.predict(corner_index=1, entry_speed=200.0, brake_point=0.4, gear=4)
    assert fast.predicted_time_s < slow.predicted_time_s
