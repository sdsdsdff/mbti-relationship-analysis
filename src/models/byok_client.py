"""Minimal BYOK client skeleton for provider-specific request construction.

The MVP client focuses on three responsibilities:

- build headers and payloads for a small set of supported providers;
- expose a transport interface that is easy to fake in tests;
- normalize provider responses into one JSON dictionary for downstream adapters.

The implementation is intentionally conservative and avoids assuming that real
network requests are available during local development or CI.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping, Protocol
from urllib import error, request

from src.models.prompt_packager import LLMPromptBundle, LLMMessageRole
from src.utils.config import BYOKConfig, BYOKProvider


_DEFAULT_ENDPOINTS: dict[BYOKProvider, str] = {
    BYOKProvider.OPENAI: "https://api.openai.com/v1/chat/completions",
    BYOKProvider.OPENROUTER: "https://openrouter.ai/api/v1/chat/completions",
    BYOKProvider.ANTHROPIC: "https://api.anthropic.com/v1/messages",
}


class BYOKClientError(RuntimeError):
    """Base error raised by the MVP BYOK client."""


class BYOKConfigurationError(BYOKClientError):
    """Raised when BYOK configuration is incomplete for a request."""


class BYOKTransportError(BYOKClientError):
    """Raised when the underlying HTTP transport cannot complete a request."""


class BYOKResponseError(BYOKClientError):
    """Raised when the provider returns an unusable or invalid response."""


@dataclass(frozen=True)
class HTTPRequest:
    """One normalized outgoing HTTP request for the BYOK transport layer."""

    method: str
    url: str
    headers: dict[str, str]
    json_body: dict[str, Any]
    timeout_seconds: float = 30.0


@dataclass(frozen=True)
class HTTPResponse:
    """One normalized HTTP response returned by a BYOK transport."""

    status_code: int
    headers: dict[str, str]
    body: str

    def json(self) -> Any:
        """Parse the response body as JSON."""

        try:
            return json.loads(self.body)
        except json.JSONDecodeError as exc:
            raise BYOKResponseError("provider response body is not valid JSON") from exc


class HTTPTransport(Protocol):
    """Protocol implemented by network transports used by the BYOK client."""

    def send(self, http_request: HTTPRequest) -> HTTPResponse:
        """Send the normalized HTTP request and return a normalized response."""


class LLMClientProtocol(Protocol):
    """Small protocol used by the pipeline for mockable LLM enrichment calls."""

    def analyze(self, prompt_bundle: LLMPromptBundle) -> dict[str, Any]:
        """Run one analysis request and return a decoded JSON dictionary."""


class UrllibTransport:
    """Standard-library HTTP transport used by the default MVP client."""

    def send(self, http_request: HTTPRequest) -> HTTPResponse:
        """Execute the HTTP request with `urllib` and normalize the response."""

        raw_request = request.Request(
            url=http_request.url,
            data=json.dumps(http_request.json_body).encode("utf-8"),
            headers=http_request.headers,
            method=http_request.method,
        )
        try:
            with request.urlopen(raw_request, timeout=http_request.timeout_seconds) as handle:
                response_body = handle.read().decode("utf-8")
                response_headers = {key: value for key, value in handle.headers.items()}
                return HTTPResponse(
                    status_code=handle.status,
                    headers=response_headers,
                    body=response_body,
                )
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise BYOKResponseError(
                f"provider returned HTTP {exc.code}: {error_body}"
            ) from exc
        except error.URLError as exc:
            raise BYOKTransportError(f"provider request failed: {exc.reason}") from exc


class BYOKClient:
    """Minimal provider-aware BYOK client for MVP LLM enrichment."""

    def __init__(
        self,
        config: BYOKConfig,
        *,
        transport: HTTPTransport | None = None,
    ) -> None:
        """Store resolved configuration and an optional custom transport."""

        self.config = config.resolve_api_key()
        self.transport = transport or UrllibTransport()

    def build_request(self, prompt_bundle: LLMPromptBundle) -> HTTPRequest:
        """Build one normalized HTTP request for the configured provider."""

        self._validate_config()
        return HTTPRequest(
            method="POST",
            url=self._build_url(),
            headers=self._build_headers(),
            json_body=self._build_payload(prompt_bundle),
        )

    def analyze(self, prompt_bundle: LLMPromptBundle) -> dict[str, Any]:
        """Send one provider request and return the decoded model JSON output."""

        http_request = self.build_request(prompt_bundle)
        http_response = self.transport.send(http_request)
        if http_response.status_code >= 400:
            raise BYOKResponseError(
                f"provider returned HTTP {http_response.status_code}: {http_response.body}"
            )

        provider_payload = http_response.json()
        content = self._extract_content(provider_payload)
        parsed = self._parse_json_content(content)
        if not isinstance(parsed, dict):
            raise BYOKResponseError("model response JSON must be an object")
        return parsed

    def _validate_config(self) -> None:
        """Ensure the MVP config includes the minimum provider settings."""

        if not self.config.enabled:
            raise BYOKConfigurationError("BYOK is disabled in the current configuration")
        if not self.config.api_key:
            raise BYOKConfigurationError("BYOK API key is missing")
        if self.config.provider == BYOKProvider.CUSTOM and not self.config.base_url:
            raise BYOKConfigurationError("custom BYOK provider requires a base_url")

    def _build_url(self) -> str:
        """Resolve the effective endpoint URL for the configured provider."""

        if self.config.provider == BYOKProvider.CUSTOM:
            assert self.config.base_url is not None
            return self.config.base_url.rstrip("/")
        return self.config.base_url or _DEFAULT_ENDPOINTS[self.config.provider]

    def _build_headers(self) -> dict[str, str]:
        """Build provider-specific HTTP headers for the request."""

        headers = {"Content-Type": "application/json"}

        if self.config.provider == BYOKProvider.ANTHROPIC:
            headers["x-api-key"] = self.config.api_key or ""
            headers["anthropic-version"] = "2023-06-01"
            return headers

        headers["Authorization"] = f"Bearer {self.config.api_key or ''}"
        if self.config.provider == BYOKProvider.OPENAI and self.config.organization:
            headers["OpenAI-Organization"] = self.config.organization
        if self.config.provider == BYOKProvider.OPENROUTER:
            headers["X-Title"] = "MBTI Relationship Analysis MVP"
        return headers

    def _build_payload(self, prompt_bundle: LLMPromptBundle) -> dict[str, Any]:
        """Build the provider-specific JSON payload for one analysis call."""

        if self.config.provider == BYOKProvider.ANTHROPIC:
            return self._build_anthropic_payload(prompt_bundle)

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [message.dict() for message in prompt_bundle.messages],
            "temperature": self.config.temperature,
            "response_format": {"type": prompt_bundle.response_contract.format},
        }
        if self.config.max_tokens is not None:
            payload["max_tokens"] = self.config.max_tokens
        return payload

    def _build_anthropic_payload(self, prompt_bundle: LLMPromptBundle) -> dict[str, Any]:
        """Build the Anthropics-compatible request payload."""

        system_prompt = prompt_bundle.system_prompt
        anthropic_messages = [
            {
                "role": message.role.value,
                "content": [{"type": "text", "text": message.content}],
            }
            for message in prompt_bundle.messages
            if message.role != LLMMessageRole.SYSTEM
        ]
        payload: dict[str, Any] = {
            "model": self.config.model,
            "system": system_prompt,
            "messages": anthropic_messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens or 1024,
        }
        return payload

    def _extract_content(self, provider_payload: Any) -> Any:
        """Extract the model content field from a provider response object."""

        if not isinstance(provider_payload, Mapping):
            raise BYOKResponseError("provider response JSON must be an object")

        if self.config.provider == BYOKProvider.ANTHROPIC:
            return self._extract_anthropic_content(provider_payload)

        choices = provider_payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise BYOKResponseError("provider response is missing choices[0]")
        message = choices[0].get("message")
        if not isinstance(message, Mapping) or "content" not in message:
            raise BYOKResponseError("provider response is missing choices[0].message.content")
        return message["content"]

    def _extract_anthropic_content(self, provider_payload: Mapping[str, Any]) -> Any:
        """Extract text content from an Anthropic-style response payload."""

        content_blocks = provider_payload.get("content")
        if not isinstance(content_blocks, list) or not content_blocks:
            raise BYOKResponseError("provider response is missing content blocks")
        text_fragments: list[str] = []
        for block in content_blocks:
            if isinstance(block, Mapping) and block.get("type") == "text":
                text_value = block.get("text")
                if isinstance(text_value, str):
                    text_fragments.append(text_value)
        if not text_fragments:
            raise BYOKResponseError("provider response does not contain text content")
        return "\n".join(text_fragments)

    def _parse_json_content(self, content: Any) -> Any:
        """Normalize raw provider content into one decoded JSON value."""

        if isinstance(content, Mapping):
            return dict(content)
        if isinstance(content, list):
            if len(content) == 1 and isinstance(content[0], Mapping) and "text" in content[0]:
                return self._parse_json_content(content[0]["text"])
            raise BYOKResponseError("provider response content list is not supported")
        if not isinstance(content, str):
            raise BYOKResponseError("provider response content must be text or JSON object")

        normalized = content.strip()
        if normalized.startswith("```"):
            normalized = self._strip_json_code_fence(normalized)
        try:
            return json.loads(normalized)
        except json.JSONDecodeError as exc:
            raise BYOKResponseError("model content is not valid JSON") from exc

    def _strip_json_code_fence(self, value: str) -> str:
        """Remove a fenced code block wrapper when a model returns one."""

        stripped = value.strip()
        if stripped.startswith("```json"):
            stripped = stripped[len("```json") :]
        elif stripped.startswith("```"):
            stripped = stripped[len("```") :]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
        return stripped.strip()


__all__ = [
    "BYOKClient",
    "BYOKClientError",
    "BYOKConfigurationError",
    "BYOKResponseError",
    "BYOKTransportError",
    "HTTPRequest",
    "HTTPResponse",
    "HTTPTransport",
    "LLMClientProtocol",
]
