"""FastAPI entry point.

Exposes the same tools through TWO surfaces:

* ``/api/*`` — a normal REST+OpenAPI surface. Foundry can consume this as a
  "custom OpenAPI tool" / skill by pointing at ``/openapi.json``.
* ``/mcp`` — an MCP streamable-HTTP server (mounted via the official
  ``mcp[cli]`` Python SDK). Foundry can consume this as an MCP tool via a
  project connection.

This lets us compare the two integration paths from a single deployment.
"""

from __future__ import annotations

import contextlib
import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from . import tools
from .mcp_server import mcp

load_dotenv()

TOOL_API_KEY = os.environ.get("TOOL_API_KEY", "").strip()

# Foundry custom OpenAPI tools require declaring at least one auth scheme;
# anonymous tools are not accepted. We declare this header in the schema so
# the Foundry UI will happily import the spec. At runtime, if ``TOOL_API_KEY``
# is set in the environment we enforce it; if not, we accept any (or no) value.
_api_key_scheme = APIKeyHeader(name="x-api-key", auto_error=False)


def _require_api_key(provided: str | None = Depends(_api_key_scheme)) -> None:
    if not TOOL_API_KEY:
        return
    if provided != TOOL_API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    title="Embr Foundry Tool Sample",
    description=(
        "Demo tools exposed over both an OpenAPI skill surface (/api/*) and an "
        "MCP streamable-HTTP server (/mcp). Built for the Embr × Foundry POC."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# ----- health ----------------------------------------------------------------


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", tags=["meta"])
async def index() -> dict[str, object]:
    return {
        "name": "Embr Foundry Tool Sample",
        "surfaces": {
            "openapi": "/openapi.json",
            "docs": "/docs",
            "mcp": "/mcp",
        },
    }


# ----- OpenAPI / skill surface ----------------------------------------------


class WeatherResponse(BaseModel):
    location: str
    condition: str
    temperature_c: float


class TimeResponse(BaseModel):
    timezone: str
    iso: str
    pretty: str


@app.get(
    "/api/weather",
    response_model=WeatherResponse,
    tags=["tools"],
    operation_id="getWeather",
    summary="Get the current weather for a city",
    dependencies=[Depends(_require_api_key)],
)
async def weather_route(location: str) -> WeatherResponse:
    return WeatherResponse(**tools.get_weather(location))


@app.get(
    "/api/time",
    response_model=TimeResponse,
    tags=["tools"],
    operation_id="getTime",
    summary="Get the current time in an IANA timezone",
    dependencies=[Depends(_require_api_key)],
)
async def time_route(timezone: str = "UTC") -> TimeResponse:
    try:
        return TimeResponse(**tools.get_time(timezone))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ----- MCP surface -----------------------------------------------------------
# Mount the MCP streamable-HTTP app at /mcp. Foundry (or any MCP client) can
# connect to https://<host>/mcp as a remote MCP server.
app.mount("/mcp", mcp.streamable_http_app())
