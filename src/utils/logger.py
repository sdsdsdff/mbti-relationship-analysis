"""Logging configuration and lightweight debugging helpers.

The project emphasizes explainability and auditability, so logs should be easy
to read during local development without introducing a heavy observability stack
up front. This module wraps the standard library logging package with a few MVP
helpers:

- one place to configure global log formatting and verbosity;
- a small timer context manager for measuring pipeline stages;
- safe preview helpers that avoid dumping entire chat records or secrets.
"""

from __future__ import annotations

import json
import logging
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any


DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DEBUG_LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | %(name)s | %(module)s:%(lineno)d | %(message)s"
)


def _normalize_level(level: str | int) -> int:
    """Convert a string or numeric level into a logging level constant."""

    if isinstance(level, int):
        return level

    normalized = level.strip().upper()
    resolved = getattr(logging, normalized, None)
    if isinstance(resolved, int):
        return resolved
    return logging.INFO


def configure_logging(
    level: str | int = "INFO",
    *,
    debug: bool = False,
    force: bool = False,
) -> logging.Logger:
    """Configure the root logger and return the project logger."""

    logging.basicConfig(
        level=_normalize_level(level),
        format=DEBUG_LOG_FORMAT if debug else DEFAULT_LOG_FORMAT,
        force=force,
    )
    logging.captureWarnings(True)
    return get_logger()


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a namespaced project logger."""

    return logging.getLogger(name or "mbti")


def mask_secret(value: str | None, keep: int = 4) -> str:
    """Mask a secret while keeping a short suffix for debugging."""

    if not value:
        return "<empty>"

    if keep <= 0 or len(value) <= keep:
        return "*" * len(value)

    return f"{'*' * (len(value) - keep)}{value[-keep:]}"


def preview_text(value: str, max_length: int = 240) -> str:
    """Trim long text for readable debug output."""

    collapsed = " ".join(value.split())
    if max_length <= 3:
        return collapsed[:max_length]
    if len(collapsed) <= max_length:
        return collapsed
    return f"{collapsed[: max_length - 3]}..."


def format_debug_value(value: Any, max_length: int = 240) -> str:
    """Render common Python and Pydantic values into short debug-friendly text."""

    if hasattr(value, "model_dump"):
        serializable = value.model_dump()
    elif hasattr(value, "dict"):
        serializable = value.dict()
    else:
        serializable = value

    if isinstance(serializable, str):
        return preview_text(serializable, max_length=max_length)

    try:
        rendered = json.dumps(serializable, ensure_ascii=False, default=str, sort_keys=True)
    except TypeError:
        rendered = repr(serializable)

    return preview_text(rendered, max_length=max_length)


def debug_kv(
    logger: logging.Logger,
    message: str,
    *,
    level: int = logging.DEBUG,
    max_length: int = 240,
    **fields: Any,
) -> None:
    """Log a compact key-value debug line with truncated field previews."""

    if not logger.isEnabledFor(level):
        return

    serialized_fields = ", ".join(
        f"{key}={format_debug_value(value, max_length=max_length)}"
        for key, value in sorted(fields.items())
    )
    if serialized_fields:
        logger.log(level, "%s | %s", message, serialized_fields)
        return

    logger.log(level, message)


@dataclass
class DebugTimer(AbstractContextManager["DebugTimer"]):
    """Simple context manager for timing pipeline stages during development."""

    label: str
    logger: logging.Logger | None = None
    level: int = logging.DEBUG
    _started_at: float = field(init=False, default=0.0)

    def __enter__(self) -> "DebugTimer":
        self._started_at = perf_counter()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        elapsed_ms = (perf_counter() - self._started_at) * 1000
        logger = self.logger or get_logger("mbti.timer")
        outcome = "failed" if exc_type is not None else "completed"
        logger.log(self.level, "%s %s in %.2fms", self.label, outcome, elapsed_ms)
        return False


__all__ = [
    "DEBUG_LOG_FORMAT",
    "DEFAULT_LOG_FORMAT",
    "DebugTimer",
    "configure_logging",
    "debug_kv",
    "format_debug_value",
    "get_logger",
    "mask_secret",
    "preview_text",
]
