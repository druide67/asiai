"""FastAPI application factory for the asiai web dashboard."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from asiai.web.state import AppState

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


def format_bytes_filter(n: int) -> str:
    """Jinja2 filter: format bytes to human-readable."""
    if n <= 0:
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} PB"


def format_number_filter(n: float, decimals: int = 1) -> str:
    """Jinja2 filter: format number with fixed decimals."""
    if n is None:
        return "—"
    return f"{n:.{decimals}f}"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Same-origin check for state-changing requests (CSRF protection)
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            origin = request.headers.get("origin", "")
            host = request.headers.get("host", "")

            # Fallback to Referer header if Origin is absent
            if not origin:
                referer = request.headers.get("referer", "")
                if referer:
                    from urllib.parse import urlparse

                    parsed_ref = urlparse(referer)
                    origin = f"{parsed_ref.scheme}://{parsed_ref.netloc}"

            if origin and host:
                from urllib.parse import urlparse

                parsed = urlparse(origin)
                origin_host = parsed.netloc
                if origin_host != host:
                    from fastapi.responses import JSONResponse

                    return JSONResponse(
                        {"error": "Cross-origin request rejected"},
                        status_code=403,
                    )
            elif not origin:
                # No Origin or Referer on a state-changing request — reject
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    {"error": "Missing Origin header"},
                    status_code=403,
                )

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; "
            "connect-src 'self'; "
            "img-src 'self' data:; "
            "frame-ancestors 'none'"
        )
        return response


def create_app(state: AppState) -> FastAPI:
    """Create and configure the FastAPI application."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("asiai web dashboard starting")
        from asiai.storage.db import init_db

        init_db(state.db_path)
        yield
        logger.info("asiai web dashboard stopping")

    app = FastAPI(
        title="asiai",
        description="LLM inference dashboard for Apple Silicon",
        lifespan=lifespan,
    )

    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # Static files
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Templates
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    templates.env.filters["format_bytes"] = format_bytes_filter
    templates.env.filters["format_number"] = format_number_filter

    # Store state and templates on app for route access
    app.state.app_state = state
    app.state.templates = templates

    # Register routes
    from asiai.web.routes import register_routes

    register_routes(app)

    return app
