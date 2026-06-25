# AI-TrackEngineer

> An AI-powered race engineer for Assetto Corsa — real-time telemetry, lap-by-lap
> analysis, a physics-based Setup Lab, and a bidirectional voice assistant.

[![CI](https://github.com/megatron54/ai-track-engineer/actions/workflows/ci.yml/badge.svg)](https://github.com/megatron54/ai-track-engineer/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)

AI-TrackEngineer captures real-time telemetry from Assetto Corsa through the
Shared Memory API, analyses driving performance lap-by-lap and corner-by-corner,
and delivers intelligent feedback through a web dashboard and a local AI engineer.

## Features (by phase)

| Phase | Capability | Status |
|-------|------------|--------|
| 1 | Live telemetry capture (60 Hz) + lap segmentation + storage + web dashboard | ✅ Done (live map + timing UI; React optional) |
| 2 | Per-corner analysis + lap comparison + tyre/engine monitors | ✅ Done |
| 3 | Natural-language coaching (local LLM via Ollama) | ✅ Done |
| 4 | Real-time in-corner feedback | 🚧 Live delta vs best |
| 5 | Pattern detection + session reports | ✅ Session reports (patterns pending) |
| 6 | Bidirectional voice assistant | ⏳ Planned |
| 7 | Predictive ML models | ⏳ Planned |
| 8 | Race strategist (fuel, pit, tyres) | 🚧 Fuel + session detection |
| 9 | Physics-based Setup Lab (digital twin) | 🚧 Power/LUT parsing (packed `.acd` cars pending) |

## Tech stack

- **Language:** Python 3.12+ (`uv` package manager)
- **Telemetry:** Shared Memory (`mmap` / `ctypes`) at 60 Hz
- **AI:** Local LLM via [Ollama](https://ollama.com) (offline, private)
- **Backend:** FastAPI + WebSocket
- **Frontend:** React + Vite (added in Phase 1)
- **Storage:** InfluxDB 2.x (time-series) + SQLite (metadata)
- **Voice:** faster-whisper (STT), Piper/Edge (TTS), Silero VAD
- **ML:** scikit-learn + XGBoost

## Requirements

- Windows with Assetto Corsa installed (Shared Memory enabled).
- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/).
- Docker (for InfluxDB) and [Ollama](https://ollama.com) for AI features.

## Quick start

```bash
# 1. Install dependencies
uv sync

# 2. Copy the example environment and adjust paths if needed
cp .env.example .env

# 3. Run with simulated telemetry (no Assetto Corsa required)
uv run python -m src.main run --mock

# 4. Run against a live Assetto Corsa session
uv run python -m src.main run

# Then open the live dashboard at http://127.0.0.1:8000
# Check your environment (Assetto Corsa, services):
uv run python -m src.main doctor
```

> **Assetto Corsa path:** the app auto-detects the default Steam location.
> To override it, set `AC_INSTALL_PATH` in your `.env` (see `.env.example`).

## Development

```bash
uv run pytest tests/ -v        # run tests
uv run ruff check src/ tests/  # lint
uv run mypy src/               # type-check
```

## Branching model

This project follows a GitFlow-inspired model:

- `main` — production-ready, protected, release-tagged only.
- `develop` — integration branch; all features merge here first.
- `feature/*`, `fix/*`, `chore/*` — short-lived branches off `develop`.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

## Documentation

- [Project plan & architecture](docs/AI-TrackEngineer-Plan.md)
- [Contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) © 2026 megatron54

## Disclaimer

This is an independent, fan-made project. It is not affiliated with or endorsed
by Kunos Simulazioni. "Assetto Corsa" is a trademark of its respective owner.
