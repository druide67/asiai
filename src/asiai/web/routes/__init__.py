"""Route registration for the asiai web dashboard."""

from __future__ import annotations

from fastapi import FastAPI

from asiai.web.routes.api import router as api_router
from asiai.web.routes.bench import router as bench_router
from asiai.web.routes.dashboard import router as dashboard_router
from asiai.web.routes.doctor import router as doctor_router
from asiai.web.routes.history import router as history_router
from asiai.web.routes.monitor import router as monitor_router


def register_routes(app: FastAPI) -> None:
    """Register all route groups on the app."""
    app.include_router(dashboard_router)
    app.include_router(bench_router)
    app.include_router(history_router)
    app.include_router(monitor_router)
    app.include_router(doctor_router)
    app.include_router(api_router)
