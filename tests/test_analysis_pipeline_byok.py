"""Tests for optional BYOK enrichment inside the analysis pipeline."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from src.analysis_pipeline import analyze_file
from src.models.byok_client import BYOKResponseError
from src.models.prompt_packager import LLMPromptBundle


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class SuccessfulFakeClient:
    """Fake client returning one canned enrichment payload."""

    def __init__(self) -> None:
        """Initialize the fake client with no captured prompt yet."""

        self.prompt_bundle: LLMPromptBundle | None = None

    def analyze(self, prompt_bundle: LLMPromptBundle) -> dict[str, object]:
        """Capture the prompt and return a valid minimal LLM payload."""

        self.prompt_bundle = prompt_bundle
        return {
            "summary": "LLM 认为当前互动值得继续观察，但仍需保守解读。",
            "type_assessments": [
                {
                    "subject": "self",
                    "summary": "你可能更偏探索与表达导向，但证据不足以下定论。",
                    "confidence": 0.52,
                    "signal_ids": ["self_initiative"],
                    "candidates": [
                        {
                            "mbti_type": "ENFP",
                            "score": 0.37,
                            "why_like": ["主动推进意愿偏明显"],
                            "why_not_like": ["样本仍偏短"]
                        }
                    ]
                }
            ],
            "insights": [
                {
                    "section": "advice",
                    "title": "LLM 补充建议",
                    "summary": "继续用具体邀约来降低误读。",
                    "bullets": ["少靠猜测，多做明确确认"],
                    "confidence": 0.63,
                    "signal_ids": ["self_initiative"]
                }
            ],
            "uncertainty_notes": ["没有更多背景资料"],
        }


class FailingFakeClient:
    """Fake client raising one controlled BYOK error."""

    def analyze(self, prompt_bundle: LLMPromptBundle) -> dict[str, object]:
        """Raise a predictable response error for fallback tests."""

        raise BYOKResponseError("mock provider failure")


def _write_config(payload: dict[str, object]) -> Path:
    """Write a temporary JSON config file for one pipeline test."""

    temp_dir = Path(tempfile.mkdtemp())
    config_path = temp_dir / "config.json"
    config_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return config_path


def test_pipeline_uses_llm_enrichment_when_configured() -> None:
    """It appends LLM cards and marks metadata when BYOK succeeds."""

    config_path = _write_config(
        {
            "byok": {
                "enabled": True,
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "api_key": "test-key",
            }
        }
    )
    fake_client = SuccessfulFakeClient()

    artifacts = analyze_file(
        FIXTURES_DIR / "flirty_positive_chat.md",
        self_names=["Me"],
        config_path=config_path,
        background_info={"relationship_goal": "更稳地推进互动"},
        llm_client=fake_client,
    )

    llm_metadata = artifacts.report.metadata["llm_enrichment"]
    llm_card_ids = {
        card.card_id
        for section in artifacts.report.sections
        for card in section.cards
        if card.card_id.startswith("llm_")
    }

    assert llm_metadata["attempted"] is True
    assert llm_metadata["used"] is True
    assert llm_metadata["fallback_reason"] is None
    assert llm_metadata["card_count"] >= 3
    assert "llm_type_self_0" in llm_card_ids
    assert fake_client.prompt_bundle is not None
    assert fake_client.prompt_bundle.metadata["has_background_info"] is True


def test_pipeline_falls_back_when_byok_disabled() -> None:
    """It keeps the heuristic-only report when BYOK is disabled."""

    config_path = _write_config(
        {
            "byok": {
                "enabled": False,
                "provider": "openai",
                "model": "gpt-4.1-mini",
            }
        }
    )

    artifacts = analyze_file(
        FIXTURES_DIR / "flirty_positive_chat.md",
        self_names=["Me"],
        config_path=config_path,
    )

    llm_metadata = artifacts.report.metadata["llm_enrichment"]
    llm_cards = [
        card
        for section in artifacts.report.sections
        for card in section.cards
        if card.card_id.startswith("llm_")
    ]

    assert llm_metadata["enabled"] is False
    assert llm_metadata["attempted"] is False
    assert llm_metadata["used"] is False
    assert llm_metadata["fallback_reason"] == "disabled"
    assert llm_cards == []


def test_pipeline_falls_back_when_api_key_is_missing() -> None:
    """It skips enrichment and records a missing-key fallback reason."""

    config_path = _write_config(
        {
            "byok": {
                "enabled": True,
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "api_key_env": "MBTI_TEST_MISSING_KEY",
            }
        }
    )

    artifacts = analyze_file(
        FIXTURES_DIR / "flirty_positive_chat.md",
        self_names=["Me"],
        config_path=config_path,
    )

    llm_metadata = artifacts.report.metadata["llm_enrichment"]

    assert llm_metadata["enabled"] is True
    assert llm_metadata["attempted"] is False
    assert llm_metadata["used"] is False
    assert llm_metadata["fallback_reason"] == "missing_api_key"


def test_pipeline_falls_back_when_llm_client_errors() -> None:
    """It preserves the heuristic report when the injected LLM client fails."""

    config_path = _write_config(
        {
            "byok": {
                "enabled": True,
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "api_key": "test-key",
            }
        }
    )

    artifacts = analyze_file(
        FIXTURES_DIR / "flirty_positive_chat.md",
        self_names=["Me"],
        config_path=config_path,
        llm_client=FailingFakeClient(),
    )

    llm_metadata = artifacts.report.metadata["llm_enrichment"]
    llm_cards = [
        card
        for section in artifacts.report.sections
        for card in section.cards
        if card.card_id.startswith("llm_")
    ]

    assert artifacts.signal_set.signals
    assert artifacts.report.sections
    assert llm_metadata["attempted"] is True
    assert llm_metadata["used"] is False
    assert llm_metadata["fallback_reason"] == "client_error"
    assert llm_metadata["error_type"] == "BYOKResponseError"
    assert llm_cards == []
