"""AI layer: context building, LLM clients and the race engineer advisor."""

from __future__ import annotations

from src.ai.advisor import RaceEngineerAdvisor
from src.ai.context_builder import build_lap_context
from src.ai.llm import LLMClient
from src.ai.models import Priority, Recommendation
from src.ai.ollama_client import OllamaClient

__all__ = [
    "LLMClient",
    "OllamaClient",
    "Priority",
    "RaceEngineerAdvisor",
    "Recommendation",
    "build_lap_context",
]
