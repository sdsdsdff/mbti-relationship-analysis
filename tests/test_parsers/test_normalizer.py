"""Tests for the lightweight conversation normalization layer."""

from src.parsers.normalizer import ConversationNormalizer
from src.parsers.schema import MessageRole
from src.parsers.text_parser import TextParser


def test_normalizer_merges_self_aliases_and_fills_defaults() -> None:
    """It merges duplicate self aliases and backfills title and metadata."""

    parser = TextParser(self_names=["Me", "我"])
    conversation = parser.parse_text(
        "[2024-03-01 09:00] Me:  Hi   there  \n"
        "[2024-03-01 09:01] Alex: Hello\n"
        "[2024-03-01 09:02] 我:   好呀   \n",
        source_ref="mixed_alias.txt",
    )

    normalized = ConversationNormalizer().normalize(
        conversation,
        default_timezone="Asia/Shanghai",
        default_language="zh-CN",
    )

    self_participants = [
        participant for participant in normalized.participants if participant.role == MessageRole.SELF
    ]

    assert normalized.title == "Mixed Alias"
    assert normalized.timezone == "Asia/Shanghai"
    assert normalized.language == "zh-CN"
    assert len(self_participants) == 1
    assert set(self_participants[0].aliases) == {"Me", "我"}
    assert normalized.messages[0].text == "Hi there"
    assert normalized.messages[2].speaker_id == self_participants[0].participant_id
    assert normalized.metadata["message_count"] == 3
    assert normalized.metadata["title_was_inferred"] is True


def test_normalizer_infers_single_counterpart_as_other() -> None:
    """It upgrades one remaining non-self participant to the other role."""

    parser = TextParser(self_names=["Me"])
    conversation = parser.parse_text(
        "Me: ping\n"
        "Alex: pong\n",
        source_ref="simple.txt",
    )

    normalized = ConversationNormalizer().normalize(conversation)
    other_participant = next(
        participant for participant in normalized.participants if participant.display_name == "Alex"
    )

    assert other_participant.role == MessageRole.OTHER
    assert normalized.messages[1].speaker_role == MessageRole.OTHER
    assert normalized.metadata["participant_roles"]["other"] == 1
