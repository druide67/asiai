"""MCP server instance and lifespan for asiai.

The server detects inference engines once at startup (via lifespan)
and shares them across all tool/resource calls through MCPContext.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from mcp.server.fastmcp import FastMCP

from asiai.engines.base import InferenceEngine
from asiai.storage.db import DEFAULT_DB_PATH, init_db

logger = logging.getLogger("asiai.mcp")


@dataclass
class MCPContext:
    """Shared state across all MCP tool calls."""

    engines: list[InferenceEngine] = field(default_factory=list)
    db_path: str = DEFAULT_DB_PATH
    last_bench_ts: float = 0.0


@asynccontextmanager
async def mcp_lifespan(server: FastMCP) -> AsyncIterator[MCPContext]:
    """Initialize engine detection and database on server start."""
    from asiai.cli import _discover_engines

    logger.info("asiai MCP server starting -- detecting engines...")
    engines = _discover_engines()
    db_path = DEFAULT_DB_PATH
    init_db(db_path)
    logger.info("Detected %d engine(s), DB at %s", len(engines), db_path)

    ctx = MCPContext(engines=engines, db_path=db_path)
    try:
        yield ctx
    finally:
        logger.info("asiai MCP server shutting down")


mcp = FastMCP(
    name="asiai",
    instructions=(
        "asiai monitors and benchmarks local LLM inference engines on Apple Silicon Macs. "
        "Use these tools to check engine health, list loaded models, run benchmarks, "
        "get hardware-aware recommendations, and query performance history. "
        "All tools work locally -- no cloud API calls. "
        "The 'run_benchmark' tool is the only active operation (takes 30-120s). "
        "All other tools are read-only and return in <2 seconds."
    ),
    lifespan=mcp_lifespan,
)


def _do_registration(engines: list[InferenceEngine]) -> None:
    """Non-blocking agent registration at startup."""
    try:
        from asiai.collectors.system import collect_hw_chip, collect_memory
        from asiai.community import register_agent

        chip = collect_hw_chip()
        mem = collect_memory()
        ram_gb = round(mem.total / (1024**3)) if mem.total > 0 else 0
        engine_names = [e.name for e in engines]

        result = register_agent(
            chip=chip,
            ram_gb=ram_gb,
            engines=engine_names,
        )
        if result.success:
            logger.info("Agent registered (#%d) — api.asiai.dev", result.total_agents)
        elif result.error:
            logger.warning("Agent registration failed: %s", result.error)
    except Exception as exc:
        logger.warning("Agent registration error: %s", exc)


def serve(
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8900,
    register: bool = False,
) -> None:
    """Start the MCP server with the specified transport.

    Args:
        transport: "stdio" (Claude Code), "sse", or "streamable-http".
        host: Bind address for SSE/HTTP.
        port: Port for SSE/HTTP.
        register: Opt-in registration with asiai agent network.
    """
    # Import tools and resources to register them on the mcp instance
    import asiai.mcp.resources  # noqa: F401
    import asiai.mcp.tools  # noqa: F401

    # Agent registration (non-blocking, best-effort)
    if register:
        from asiai.cli import _discover_engines

        _do_registration(_discover_engines())

    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "sse":
        mcp.settings.host = host
        mcp.settings.port = port
        mcp.run(transport="sse")
    else:
        mcp.settings.host = host
        mcp.settings.port = port
        mcp.run(transport="streamable-http")
