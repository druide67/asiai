"""Allow running the MCP server via ``python -m asiai.mcp``."""

from asiai.mcp.server import serve

serve(transport="stdio")
