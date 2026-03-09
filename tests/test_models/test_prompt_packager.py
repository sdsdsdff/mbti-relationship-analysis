"""Tests for the provider-agnostic prompt packaging layer."""

from __future__ import annotations

from datetime import datetime

from src.analyzers.signal_schema import (
    BehaviorSignal,
    BehaviorSignalSet,
    BehaviorSignalType,
    SignalConfidence,
    SignalStrength,
    SignalSubject,
)
from src.models.prompt_packager import LLMPromptPackager
from src.parsers.schema import (
    Conversation,
    ConversationParticipant,
    ConversationSourceKind,
    Message,
    MessageRole,
)


def _build_conversation() -> Conversation:
    """Create a minimal normalized conversation fixture for prompt tests."""

    return Conversation(
        conversation_id="demo-chat",
        title="Demo Chat",
        source_kind=ConversationSourceKind.MARKDOWN,
        participants=[
            ConversationParticipant(
                participant_id="self",
                display_name="Me",
                role=MessageRole.SELF,
            ),
            ConversationParticipant(
                participant_id="other",
                display_name="Them",
                role=MessageRole.OTHER,
            ),
        ],
        messages=[
            Message(
                message_id="m1",
                sequence_no=1,
                speaker_id="self",
                speaker_name="Me",
                speaker_role=MessageRole.SELF,
                text="今天晚上有空吗？",
                normalized_text="今天晚上有空吗？",
                sent_at=datetime(2026, 3, 8, 20, 0, 0),
            ),
            Message(
                message_id="m2",
                sequence_no=2,
                speaker_id="other",
                speaker_name="Them",
                speaker_role=MessageRole.OTHER,
                text="有呀，我们可以一起吃饭。",
                normalized_text="有呀，我们可以一起吃饭。",
                sent_at=datetime(2026, 3, 8, 20, 2, 0),
            ),
        ],
        language="zh-CN",
        timezone="UTC",
    )


def _build_signal_set() -> BehaviorSignalSet:
    """Create a minimal heuristic signal set fixture for prompt tests."""

    return BehaviorSignalSet(
        signal_set_id="signals-demo-chat",
        conversation_id="demo-chat",
        extractor_name="heuristics",
        extractor_version="0.1.0",
        signals=[
            BehaviorSignal(
                signal_id="signal_initiative_self",
                type=BehaviorSignalType.INITIATIVE,
                subject=SignalSubject.SELF,
                participant_id="self",
                summary="你先发起了具体邀约。",
                strength=SignalStrength(score=0.72),
                confidence=SignalConfidence(score=0.83),
                message_ids=["m1"],
            ),
            BehaviorSignal(
                signal_id="signal_warmth_other",
                type=BehaviorSignalType.EMOTIONAL_WARMTH,
                subject=SignalSubject.OTHER,
                participant_id="other",
                summary="对方回复积极，也给出一起吃饭的具体意愿。",
                strength=SignalStrength(score=0.68),
                confidence=SignalConfidence(score=0.74),
                message_ids=["m2"],
            ),
        ],
    )


def test_prompt_packager_builds_conservative_messages() -> None:
    """It produces a two-message prompt bundle with conservative guidance."""

    bundle = LLMPromptPackager().build(_build_conversation(), _build_signal_set())

    assert len(bundle.messages) == 2
    assert "evidence-based" in bundle.system_prompt
    assert "uncertainty" in bundle.system_prompt
    assert "Avoid deterministic MBTI typing".lower() in bundle.system_prompt.lower()
    assert bundle.metadata["conversation_id"] == "demo-chat"
    assert bundle.metadata["signal_count"] == 2
    assert '"conversation_id": "demo-chat"' in bundle.messages[1].content
    assert '"signal_id": "signal_initiative_self"' in bundle.messages[1].content


def test_prompt_packager_includes_background_info_when_provided() -> None:
    """It embeds optional background info into the serialized analysis context."""

    bundle = LLMPromptPackager().build(
        _build_conversation(),
        _build_signal_set(),
        background_info={"relationship_goal": "想更稳地推进了解", "known_context": ["近期都很忙"]},
    )

    assert bundle.metadata["has_background_info"] is True
    assert '"relationship_goal": "想更稳地推进了解"' in bundle.messages[1].content
    assert '"known_context": [' in bundle.messages[1].content


def test_prompt_packager_exposes_response_contract() -> None:
    """It requests a compact JSON response contract for downstream adapters."""

    bundle = LLMPromptPackager().build(_build_conversation(), _build_signal_set())

    assert bundle.response_contract.format == "json_object"
    assert bundle.response_contract.required_fields == [
        "summary",
        "type_assessments",
        "insights",
        "uncertainty_notes",
    ]
    assert '"section": "overview|self|other|relationship|advice"' in bundle.messages[1].content
