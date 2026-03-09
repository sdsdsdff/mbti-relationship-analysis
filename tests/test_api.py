"""API smoke tests for the local FastAPI wrapper."""

import asyncio
from pathlib import Path

from src.api import app

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class DummyUploadFile:
    """Minimal upload stub for exercising the route logic directly."""

    def __init__(self, *, filename: str, content: bytes, content_type: str) -> None:
        self.filename = filename
        self.content_type = content_type
        self._content = content

    async def read(self) -> bytes:
        return self._content

    async def close(self) -> None:
        return None


def _route_endpoint(path: str, method: str):
    """Find the endpoint callable for one declared API route."""

    for route in app.routes:
        matches_path = getattr(route, "path", None) == path
        supports_method = method in getattr(route, "methods", set())
        if matches_path and supports_method:
            return route.endpoint
    raise AssertionError(f"Route not found: {method} {path}")


def test_health_endpoint_returns_ok() -> None:
    """The health endpoint should expose a tiny JSON payload."""

    payload = _route_endpoint("/api/health", "GET")()

    assert payload == {
        "status": "ok",
        "service": "mbti-relationship-analysis-api",
    }


def test_analyze_endpoint_accepts_uploaded_transcript() -> None:
    """The analyze endpoint should reuse the existing pipeline for uploads."""

    endpoint = _route_endpoint("/api/analyze", "POST")
    upload = DummyUploadFile(
        filename="flirty_positive_chat.md",
        content=(FIXTURES_DIR / "flirty_positive_chat.md").read_bytes(),
        content_type="text/markdown",
    )
    payload = asyncio.run(endpoint(upload, "Me, 自己"))

    assert payload["status"] == "ok"
    assert payload["input"]["filename"] == "flirty_positive_chat.md"
    assert payload["input"]["self_names"] == ["Me", "自己"]
    assert payload["report"]["sections"]
    assert payload["artifacts"]["conversation"]["title"] == "Late Night Flirty Chat"
    assert any(
        participant["role"] == "self"
        for participant in payload["artifacts"]["conversation"]["participants"]
    )
