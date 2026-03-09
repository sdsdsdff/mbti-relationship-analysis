"""Integration-style tests that import the fixture transcript files."""

from pathlib import Path

from src.parsers.parser_factory import ParserFactory
from src.parsers.schema import ConversationSourceKind, MessageRole


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_markdown_fixture_import() -> None:
    """It imports the sample Markdown transcript fixture."""

    conversation = ParserFactory.parse_file(
        FIXTURES_DIR / "sample_chat.md",
        self_names=["Me"],
    )

    assert conversation.title == "Cozy Evening Chat"
    assert conversation.source_kind == ConversationSourceKind.MARKDOWN
    assert conversation.message_count == 3
    assert conversation.messages[0].speaker_role == MessageRole.SELF


def test_text_fixture_import() -> None:
    """It imports the sample text transcript fixture."""

    conversation = ParserFactory.parse_file(
        FIXTURES_DIR / "sample_chat.txt",
        self_names=["我"],
    )

    assert conversation.source_kind == ConversationSourceKind.TEXT_EXPORT
    assert conversation.message_count == 3
    assert conversation.messages[0].speaker_role == MessageRole.SELF
    assert conversation.messages[-1].text == "晚安"
