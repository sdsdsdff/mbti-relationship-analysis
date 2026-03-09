"""Tests for the simple text conversation parser."""

from src.parsers.schema import ConversationSourceKind, MessageRole
from src.parsers.text_parser import TextParser


def test_text_parser_supports_timestamped_and_plain_lines() -> None:
    """It parses both supported text message line formats."""

    parser = TextParser(self_names=["我"])
    conversation = parser.parse_text(
        "[2024-02-02 20:00] 我: 到家了\n"
        "Alex: 好的，早点休息\n",
        source_ref="chat.txt",
    )

    assert conversation.conversation_id == "chat"
    assert conversation.source_kind == ConversationSourceKind.TEXT_EXPORT
    assert conversation.message_count == 2
    assert conversation.messages[0].speaker_role == MessageRole.SELF
    assert conversation.messages[0].sent_at is not None
    assert conversation.messages[1].speaker_name == "Alex"


def test_text_parser_records_skipped_lines() -> None:
    """It keeps parsing when unsupported text lines appear."""

    parser = TextParser()
    conversation = parser.parse_text(
        "System notice\n"
        "Alex：收到\n",
        source_ref="plain.txt",
    )

    assert conversation.message_count == 1
    assert len(conversation.parser_warnings) == 1
    assert "line 1" in conversation.parser_warnings[0]
