"""Web dashboard for asiai (optional dependency: FastAPI + Jinja2 + uvicorn)."""

from __future__ import annotations

HAS_FASTAPI = False

try:
    import fastapi  # noqa: F401

    HAS_FASTAPI = True
except ImportError:
    pass
