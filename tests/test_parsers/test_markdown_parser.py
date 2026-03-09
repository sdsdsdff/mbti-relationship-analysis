"""Tests for the simple Markdown conversation parser."""

from src.parsers.markdown_parser import MarkdownParser
from src.parsers.schema import ConversationSourceKind, MessageRole


def test_markdown_parser_converts_messages_and_title() -> None:
    """It parses headings and Markdown list items into normalized messages."""

    parser = MarkdownParser(self_names=["Me"])
    conversation = parser.parse_text(
        "# Weekend Chat\n"
        "- [2024-01-01 09:00] Me: Happy new year!\n"
        "- [2024-01-01 09:01] Alex: Same to you\n",
        source_ref="weekend.md",
    )

    assert conversation.conversation_id == "weekend"
    assert conversation.title == "Weekend Chat"
    assert conversation.source_kind == ConversationSourceKind.MARKDOWN
    assert conversation.message_count == 2
    assert conversation.messages[0].speaker_role == MessageRole.SELF
    assert conversation.messages[0].sent_at is not None
    assert conversation.messages[1].speaker_name == "Alex"
    assert conversation.messages[1].normalized_text == "Same to you"


def test_markdown_parser_records_skipped_lines() -> None:
    """It keeps parsing when unsupported Markdown lines appear."""

    parser = MarkdownParser()
    conversation = parser.parse_text(
        "# Chat\n"
        "This line is ignored\n"
        "* Alex: Hello\n",
        source_ref="chat.md",
    )

    assert conversation.message_count == 1
    assert len(conversation.parser_warnings) == 1
    assert "line 2" in conversation.parser_warnings[0]
