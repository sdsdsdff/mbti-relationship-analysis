"""Tests for the MVP BYOK client skeleton."""

from __future__ import annotations

import json

from src.models.byok_client import (
    BYOKClient,
    BYOKConfigurationError,
    HTTPRequest,
    HTTPResponse,
)
from src.models.prompt_packager import LLMMessage, LLMPromptBundle, LLMMessageRole
from src.utils.config import BYOKConfig, BYOKProvider


class FakeTransport:
    """Small fake transport used by the client tests."""

    def __init__(self, response: HTTPResponse) -> None:
        """Store one canned response and collect outgoing requests."""

        self.response = response
        self.requests: list[HTTPRequest] = []

    def send(self, http_request: HTTPRequest) -> HTTPResponse:
        """Return the canned response and record the outgoing request."""

        self.requests.append(http_request)
        return self.response


def _build_prompt_bundle() -> LLMPromptBundle:
    """Create a compact prompt bundle fixture for client tests."""

    return LLMPromptBundle(
        system_prompt="Return cautious JSON only.",
        messages=[
            LLMMessage(role=LLMMessageRole.SYSTEM, content="Return cautious JSON only."),
            LLMMessage(
                role=LLMMessageRole.USER,
                content='{"conversation": {"conversation_id": "demo-chat"}}',
            ),
        ],
    )


def test_byok_client_builds_openai_request() -> None:
    """It builds an OpenAI-compatible request with authorization headers."""

    client = BYOKClient(
        BYOKConfig(
            enabled=True,
            provider=BYOKProvider.OPENAI,
            model="gpt-4.1-mini",
            api_key="test-key",
            organization="org-demo",
            max_tokens=500,
        )
    )

    request_payload = client.build_request(_build_prompt_bundle())

    assert request_payload.url == "https://api.openai.com/v1/chat/completions"
    assert request_payload.headers["Authorization"] == "Bearer test-key"
    assert request_payload.headers["OpenAI-Organization"] == "org-demo"
    assert request_payload.json_body["model"] == "gpt-4.1-mini"
    assert request_payload.json_body["response_format"] == {"type": "json_object"}
    assert request_payload.json_body["max_tokens"] == 500


def test_byok_client_builds_openrouter_request() -> None:
    """It builds an OpenRouter-compatible request with the expected endpoint."""

    client = BYOKClient(
        BYOKConfig(
            enabled=True,
            provider=BYOKProvider.OPENROUTER,
            model="openrouter/auto",
            api_key="test-key",
        )
    )

    request_payload = client.build_request(_build_prompt_bundle())

    assert request_payload.url == "https://openrouter.ai/api/v1/chat/completions"
    assert request_payload.headers["Authorization"] == "Bearer test-key"
    assert request_payload.headers["X-Title"] == "MBTI Relationship Analysis MVP"


def test_byok_client_builds_anthropic_request() -> None:
    """It builds an Anthropic-compatible payload with top-level system text."""

    client = BYOKClient(
        BYOKConfig(
            enabled=True,
            provider=BYOKProvider.ANTHROPIC,
            model="claude-3-5-haiku-latest",
            api_key="test-key",
        )
    )

    request_payload = client.build_request(_build_prompt_bundle())

    assert request_payload.url == "https://api.anthropic.com/v1/messages"
    assert request_payload.headers["x-api-key"] == "test-key"
    assert request_payload.headers["anthropic-version"] == "2023-06-01"
    assert request_payload.json_body["system"] == "Return cautious JSON only."
    assert request_payload.json_body["messages"][0]["content"][0]["text"].startswith("{")
    assert request_payload.json_body["max_tokens"] == 1024


def test_byok_client_requires_custom_base_url() -> None:
    """It rejects custom providers that do not specify a base URL."""

    client = BYOKClient(
        BYOKConfig(
            enabled=True,
            provider=BYOKProvider.CUSTOM,
            model="custom-model",
            api_key="test-key",
        )
    )

    try:
        client.build_request(_build_prompt_bundle())
    except BYOKConfigurationError as exc:
        assert "base_url" in str(exc)
        return

    raise AssertionError("expected BYOKConfigurationError for missing custom base_url")


def test_byok_client_parses_openai_json_response() -> None:
    """It decodes OpenAI-style response content into a JSON dictionary."""

    fake_transport = FakeTransport(
        HTTPResponse(
            status_code=200,
            headers={},
            body=json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "summary": "样本偏短。",
                                        "type_assessments": [],
                                        "insights": [],
                                        "uncertainty_notes": ["消息数量有限"],
                                    }
                                )
                            }
                        }
                    ]
                }
            ),
        )
    )
    client = BYOKClient(
        BYOKConfig(
            enabled=True,
            provider=BYOKProvider.OPENAI,
            model="gpt-4.1-mini",
            api_key="test-key",
        ),
        transport=fake_transport,
    )

    result = client.analyze(_build_prompt_bundle())

    assert result["summary"] == "样本偏短。"
    assert result["uncertainty_notes"] == ["消息数量有限"]
    assert fake_transport.requests[0].headers["Authorization"] == "Bearer test-key"


def test_byok_client_parses_anthropic_json_response() -> None:
    """It decodes Anthropic-style text blocks into a JSON dictionary."""

    fake_transport = FakeTransport(
        HTTPResponse(
            status_code=200,
            headers={},
            body=json.dumps(
                {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "summary": "观察仍需保守。",
                                    "type_assessments": [],
                                    "insights": [],
                                    "uncertainty_notes": ["背景信息为空"],
                                }
                            ),
                        }
                    ]
                }
            ),
        )
    )
    client = BYOKClient(
        BYOKConfig(
            enabled=True,
            provider=BYOKProvider.ANTHROPIC,
            model="claude-3-5-haiku-latest",
            api_key="test-key",
        ),
        transport=fake_transport,
    )

    result = client.analyze(_build_prompt_bundle())

    assert result["summary"] == "观察仍需保守。"
    assert result["uncertainty_notes"] == ["背景信息为空"]
