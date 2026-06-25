# Contributing to AI-TrackEngineer

Thanks for your interest! This document describes the development workflow.

## Branching model (GitFlow-inspired)

```
main      ← production-ready. Protected. Only updated via PR from develop + a version tag.
  ▲
develop   ← integration branch. Every feature merges here first.
  ▲
feature/* ← one branch per feature/phase (e.g. feature/phase1-telemetry)
fix/*     ← bug fixes
chore/*   ← tooling, CI, configuration, docs scaffolding
```

### Rules

1. **Never commit directly to `main` or `develop`.** Both are protected.
2. Branch off `develop`:
   ```bash
   git checkout develop && git pull
   git checkout -b feature/<short-name>
   ```
3. Commit in small, focused steps using **Conventional Commits** (see below).
4. Push and open a PR **into `develop`**:
   ```bash
   git push -u origin feature/<short-name>
   gh pr create --base develop --fill
   ```
5. CI (lint + type-check + tests with 80% coverage) must pass before merge.
6. When `develop` reaches a stable milestone, open a PR **`develop → main`** and
   tag a release (`vX.Y.Z`).

## Commit messages (Conventional Commits)

```
<type>(<scope>): <subject>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`.

Examples:

```
feat(telemetry): add 60Hz shared-memory reader
test(lap-segmenter): cover finish-line crossing edge cases
chore(ci): add ruff + mypy + pytest workflow
```

A commit template is provided. Enable it with:

```bash
git config commit.template .gitmessage
```

## Code quality

Before pushing, run:

```bash
uv run ruff check src/ tests/
uv run mypy src/
uv run pytest tests/ -v
```

Standards:

- Full type hints on all functions and classes.
- Clean architecture: well-separated layers, dependency injection, ABC/Protocol
  boundaries so each layer is swappable.
- Small files (200–400 lines typical), small functions (<50 lines).
- Immutability: prefer new objects over mutation.
- No secrets in code or commits. Use `.env` (ignored) and `.env.example`.
- Robust error handling — the telemetry loop must never crash mid-session.

## Tests

- Write tests first (TDD): RED → GREEN → REFACTOR.
- Keep coverage at **80%+**.
- Use `scripts/mock_telemetry.py` to develop without Assetto Corsa running.
