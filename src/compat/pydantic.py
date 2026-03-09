"""Pydantic compatibility helpers supporting v1-style APIs on v1 or v2."""

from __future__ import annotations

try:
    from pydantic.v1 import BaseModel, Field, root_validator, validator
except ImportError:
    from pydantic import BaseModel, Field, root_validator, validator


__all__ = ["BaseModel", "Field", "root_validator", "validator"]
