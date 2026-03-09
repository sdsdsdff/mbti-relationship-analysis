"""Application configuration helpers.

This module keeps runtime configuration intentionally small for the MVP phase.
Configuration loading follows three simple rules:

1. read an optional JSON config file for local defaults;
2. overlay supported environment variables;
3. resolve BYOK secrets from direct values or provider-specific env vars.

The goal is to stay dependency-light while still supporting local development,
self-hosting, and the project's BYOK privacy model.
"""

from __future__ import annotations

import json
import os
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from src.compat.pydantic import BaseModel, Field, validator


ENV_PREFIX = "MBTI_"


class AppEnvironment(str, Enum):
    """Runtime environment for the application."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class BYOKProvider(str, Enum):
    """Supported model provider labels for BYOK mode."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    CUSTOM = "custom"


_DEFAULT_API_KEY_ENV: dict[BYOKProvider, str | None] = {
    BYOKProvider.OPENAI: "OPENAI_API_KEY",
    BYOKProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
    BYOKProvider.OPENROUTER: "OPENROUTER_API_KEY",
    BYOKProvider.CUSTOM: None,
}


def _parse_bool(value: str | bool | None, default: bool = False) -> bool:
    """Convert common env-style boolean strings into real booleans."""

    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_json_config(path: Path) -> dict[str, Any]:
    """Load a JSON config file or return an empty mapping when absent."""

    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError(f"config file must contain a JSON object: {path}")

    return data


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge two config dictionaries."""

    merged = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = value
    return merged


def _default_config_candidates() -> list[Path]:
    """Return the small set of config paths checked automatically."""

    return [
        Path("mbti.config.json"),
        Path("config.json"),
        Path("config/config.json"),
    ]


def _resolve_config_path(
    config_path: str | os.PathLike[str] | None,
    env: Mapping[str, str],
) -> Path | None:
    """Resolve the explicit or default config path when one exists."""

    if config_path is not None:
        return Path(config_path)

    env_path = env.get(f"{ENV_PREFIX}CONFIG_FILE")
    if env_path:
        return Path(env_path)

    for candidate in _default_config_candidates():
        if candidate.exists():
            return candidate

    return None


def _env_overrides(env: Mapping[str, str]) -> dict[str, Any]:
    """Translate supported environment variables into config overrides."""

    overrides: dict[str, Any] = {}

    if f"{ENV_PREFIX}APP_ENV" in env:
        overrides["environment"] = env[f"{ENV_PREFIX}APP_ENV"]
    if f"{ENV_PREFIX}DEBUG" in env:
        overrides["debug"] = _parse_bool(env[f"{ENV_PREFIX}DEBUG"])
    if f"{ENV_PREFIX}LOG_LEVEL" in env:
        overrides["log_level"] = env[f"{ENV_PREFIX}LOG_LEVEL"]
    if f"{ENV_PREFIX}DEFAULT_LOCALE" in env:
        overrides["default_locale"] = env[f"{ENV_PREFIX}DEFAULT_LOCALE"]
    if f"{ENV_PREFIX}DEFAULT_TIMEZONE" in env:
        overrides["default_timezone"] = env[f"{ENV_PREFIX}DEFAULT_TIMEZONE"]
    if f"{ENV_PREFIX}DATA_DIR" in env:
        overrides["data_dir"] = env[f"{ENV_PREFIX}DATA_DIR"]

    byok_overrides: dict[str, Any] = {}
    if f"{ENV_PREFIX}BYOK_ENABLED" in env:
        byok_overrides["enabled"] = _parse_bool(env[f"{ENV_PREFIX}BYOK_ENABLED"])
    if f"{ENV_PREFIX}BYOK_PROVIDER" in env:
        byok_overrides["provider"] = env[f"{ENV_PREFIX}BYOK_PROVIDER"]
    if f"{ENV_PREFIX}BYOK_MODEL" in env:
        byok_overrides["model"] = env[f"{ENV_PREFIX}BYOK_MODEL"]
    if f"{ENV_PREFIX}BYOK_BASE_URL" in env:
        byok_overrides["base_url"] = env[f"{ENV_PREFIX}BYOK_BASE_URL"]
    if f"{ENV_PREFIX}BYOK_API_KEY" in env:
        byok_overrides["api_key"] = env[f"{ENV_PREFIX}BYOK_API_KEY"]
    if f"{ENV_PREFIX}BYOK_API_KEY_ENV" in env:
        byok_overrides["api_key_env"] = env[f"{ENV_PREFIX}BYOK_API_KEY_ENV"]
    if f"{ENV_PREFIX}BYOK_ORGANIZATION" in env:
        byok_overrides["organization"] = env[f"{ENV_PREFIX}BYOK_ORGANIZATION"]
    if f"{ENV_PREFIX}BYOK_TEMPERATURE" in env:
        byok_overrides["temperature"] = float(env[f"{ENV_PREFIX}BYOK_TEMPERATURE"])
    if f"{ENV_PREFIX}BYOK_MAX_TOKENS" in env:
        byok_overrides["max_tokens"] = int(env[f"{ENV_PREFIX}BYOK_MAX_TOKENS"])

    if byok_overrides:
        overrides["byok"] = byok_overrides

    return overrides


class BYOKConfig(BaseModel):
    """Bring-your-own-key model configuration."""

    enabled: bool = Field(
        default=False,
        description="Whether external model access is enabled in the current runtime.",
    )
    provider: BYOKProvider = Field(
        default=BYOKProvider.OPENAI,
        description="Provider label used for API routing and secret lookup.",
    )
    model: str = Field(
        default="gpt-4.1-mini",
        description="Default model name for the configured provider.",
    )
    api_key: str | None = Field(
        default=None,
        description="Resolved API key value, populated from config or environment.",
    )
    api_key_env: str | None = Field(
        default=None,
        description="Environment variable name used to resolve the API key.",
    )
    base_url: str | None = Field(
        default=None,
        description="Optional custom API base URL.",
    )
    organization: str | None = Field(
        default=None,
        description="Optional organization or workspace identifier.",
    )
    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="Default sampling temperature for analysis calls.",
    )
    max_tokens: int | None = Field(
        default=None,
        gt=0,
        description="Optional output token limit for model calls.",
    )

    class Config:
        anystr_strip_whitespace = True

    @validator("api_key_env", always=True)
    def default_api_key_env(cls, value: str | None, values: dict[str, Any]) -> str | None:
        """Backfill the provider-specific API key env name when omitted."""

        if value is not None:
            return value

        provider = values.get("provider", BYOKProvider.OPENAI)
        return _DEFAULT_API_KEY_ENV.get(provider)

    def resolve_api_key(self, env: Mapping[str, str] | None = None) -> "BYOKConfig":
        """Return a copy with `api_key` resolved from the configured env var when needed."""

        if self.api_key:
            return self

        env_mapping = env or os.environ
        if self.api_key_env:
            resolved = env_mapping.get(self.api_key_env)
            if resolved:
                return self.copy(update={"api_key": resolved})

        return self


class AppConfig(BaseModel):
    """Top-level runtime configuration used by the MVP codebase."""

    environment: AppEnvironment = Field(
        default=AppEnvironment.DEVELOPMENT,
        description="Current runtime environment.",
    )
    debug: bool = Field(default=False, description="Enable debug-friendly behavior.")
    log_level: str = Field(default="INFO", description="Default application log level.")
    default_locale: str = Field(
        default="zh-CN",
        description="Default locale used for parsing and report rendering hints.",
    )
    default_timezone: str = Field(
        default="UTC",
        description="Default timezone used when source timestamps are ambiguous.",
    )
    data_dir: str = Field(
        default="data",
        description="Base directory for local runtime data and caches.",
    )
    byok: BYOKConfig = Field(
        default_factory=BYOKConfig,
        description="Bring-your-own-key model settings.",
    )

    class Config:
        anystr_strip_whitespace = True

    @validator("log_level")
    def normalize_log_level(cls, value: str) -> str:
        """Normalize the configured log level to uppercase."""

        return value.upper()

    def resolve_secrets(self, env: Mapping[str, str] | None = None) -> "AppConfig":
        """Return a copy with BYOK secrets resolved from the provided environment."""

        return self.copy(update={"byok": self.byok.resolve_api_key(env)})


def load_config(
    config_path: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> AppConfig:
    """Load application configuration from JSON defaults and environment overrides."""

    env_mapping = env or os.environ
    resolved_path = _resolve_config_path(config_path, env_mapping)
    explicit_config_requested = config_path is not None or bool(env_mapping.get(f"{ENV_PREFIX}CONFIG_FILE"))

    if explicit_config_requested and resolved_path is not None and not resolved_path.exists():
        raise FileNotFoundError(f"config file not found: {resolved_path}")

    file_data = _read_json_config(resolved_path) if resolved_path is not None else {}
    merged_data = _deep_merge(file_data, _env_overrides(env_mapping))
    config = AppConfig(**merged_data)
    return config.resolve_secrets(env_mapping)


__all__ = [
    "AppConfig",
    "AppEnvironment",
    "BYOKConfig",
    "BYOKProvider",
    "ENV_PREFIX",
    "load_config",
]
