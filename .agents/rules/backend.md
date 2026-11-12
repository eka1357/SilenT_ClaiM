---
trigger: glob
globs: api/**
---

# Backend rules

- Read `docs/ARCHITECTURE.md` and `docs/DATA_SPEC.md` first. Endpoints, SSE events and table names must match them exactly.
- Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2, LangGraph, httpx. `uv` for packages, `ruff` for format and lint.
- Money in integer paise. Times are timezone-aware, `Asia/Kolkata`.
- Every external call goes through `app/integrations/*` with a 4 s timeout and a fixture fallback (`replay.py`). Emit `integration.health` when the mode changes.
- Never guess an external API. Read the official docs linked in ARCHITECTURE.md; if unclear, stop and report.
- Every new behaviour gets a pytest test. Tests must not use the network unless marked `@pytest.mark.live`.
- Before saying done: `uv run ruff check . && uv run pytest -q` pass, and the path works with `DEMO_OFFLINE=1`.
