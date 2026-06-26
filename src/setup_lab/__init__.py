"""Setup Lab: consistency scoring and setup file I/O."""

from __future__ import annotations

from src.setup_lab.consistency_scorer import ConsistencyScore, score_consistency
from src.setup_lab.setup_io import apply_changes, read_setup, write_setup

__all__ = [
    "ConsistencyScore",
    "apply_changes",
    "read_setup",
    "score_consistency",
    "write_setup",
]
