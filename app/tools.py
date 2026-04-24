"""Tool implementations shared by the OpenAPI (skill) routes and the MCP server.

Keeping the core logic here means the exact same function runs regardless of
which surface Foundry is using, so we can compare the two paths apples-to-apples.
"""

from __future__ import annotations

from datetime import datetime
from random import randint
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_CONDITIONS = ["sunny", "cloudy", "rainy", "windy", "snowy"]


def get_weather(location: str) -> dict[str, str | float]:
    """Return a (fake) current weather report for a city."""
    return {
        "location": location,
        "condition": _CONDITIONS[randint(0, len(_CONDITIONS) - 1)],
        "temperature_c": float(randint(-5, 35)),
    }


def get_time(timezone: str = "UTC") -> dict[str, str]:
    """Return the current time in the given IANA timezone (e.g. 'America/New_York')."""
    try:
        tz = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {timezone!r}") from exc
    now = datetime.now(tz)
    return {
        "timezone": timezone,
        "iso": now.isoformat(),
        "pretty": now.strftime("%A, %d %B %Y %H:%M:%S %Z"),
    }
