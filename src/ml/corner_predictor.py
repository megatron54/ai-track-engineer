"""Corner-time predictor: predict time through a corner from entry conditions.

This module defines the model interface and a heuristic baseline. The real
XGBoost model is trained via ``scripts/train_models.py`` and loaded from disk;
until enough data exists (min ~50 laps per track/car), the heuristic is used.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CornerPrediction:
    """Predicted time through a corner and its confidence."""

    corner_index: int
    predicted_time_s: float
    confidence: float  # 0-1


class CornerPredictor(ABC):
    """Predict the time through a corner given entry features."""

    @abstractmethod
    def predict(
        self, corner_index: int, entry_speed: float, brake_point: float, gear: int
    ) -> CornerPrediction:
        """Return a prediction for a specific corner."""

    @abstractmethod
    def is_trained(self) -> bool:
        """Whether the model has been trained (vs heuristic fallback)."""


class HeuristicCornerPredictor(CornerPredictor):
    """Baseline predictor using a simple speed-based estimate.

    Used as the cold-start fallback until enough data exists for ML training.
    """

    def __init__(self, avg_corner_time_s: float = 5.0) -> None:
        self._base = avg_corner_time_s

    def predict(
        self, corner_index: int, entry_speed: float, brake_point: float, gear: int
    ) -> CornerPrediction:
        # Very rough: faster entry -> slightly shorter corner time.
        factor = max(0.5, 1.0 - (entry_speed - 100.0) / 500.0)
        return CornerPrediction(
            corner_index=corner_index,
            predicted_time_s=round(self._base * factor, 3),
            confidence=0.1,
        )

    def is_trained(self) -> bool:
        return False


class TrainedCornerPredictor(CornerPredictor):
    """XGBoost corner predictor loaded from a serialised model file.

    Importing ``xgboost`` is deferred to :meth:`load` so the module can be
    imported without the ML extras installed.
    """

    def __init__(self) -> None:
        self._model: object | None = None

    @classmethod
    def load(cls, path: str | Path) -> TrainedCornerPredictor:
        """Load a trained model from a ``.joblib`` file."""
        import joblib

        instance = cls()
        instance._model = joblib.load(path)
        return instance

    def predict(
        self, corner_index: int, entry_speed: float, brake_point: float, gear: int
    ) -> CornerPrediction:
        if self._model is None:
            raise RuntimeError("model not loaded")
        import numpy as np

        features = np.array([[entry_speed, brake_point, float(gear), float(corner_index)]])
        predicted = float(self._model.predict(features)[0])  # type: ignore[union-attr]
        return CornerPrediction(
            corner_index=corner_index,
            predicted_time_s=round(predicted, 3),
            confidence=0.8,
        )

    def is_trained(self) -> bool:
        return self._model is not None
