"""MCP server surface.

Exposes the same tools as the OpenAPI routes, but over MCP's streamable-HTTP
transport. Foundry agents can consume this by registering the server URL as
an MCP tool via a project connection.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import tools

mcp = FastMCP(
    "Embr Tool Sample",
    host="0.0.0.0",
    json_response=True,
    stateless_http=True,
    streamable_http_path="/",
)


@mcp.tool()
def get_weather(location: str) -> dict[str, str | float]:
    """Get the current weather for a city."""
    return tools.get_weather(location)


@mcp.tool()
def get_time(timezone: str = "UTC") -> dict[str, str]:
    """Get the current time in an IANA timezone (e.g. 'America/New_York')."""
    return tools.get_time(timezone)
