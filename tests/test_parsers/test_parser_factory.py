"""Tests for parser auto-selection and the unified import entrypoint."""

from pathlib import Path
import tempfile

from src.parsers.markdown_parser import MarkdownParser
from src.parsers.parser_factory import ParserFactory
from src.parsers.schema import ConversationSourceKind
from src.parsers.text_parser import TextParser


def test_parser_factory_selects_parser_by_extension() -> None:
    """It chooses the expected parser implementation for each suffix."""

    assert isinstance(ParserFactory.create_parser("chat.md"), MarkdownParser)
    assert isinstance(ParserFactory.create_parser("chat.markdown"), MarkdownParser)
    assert isinstance(ParserFactory.create_parser("chat.txt"), TextParser)


def test_parser_factory_parses_file_with_unified_entrypoint() -> None:
    """It imports a text file without callers handling parser selection."""

    with tempfile.TemporaryDirectory() as temp_dir:
        file_path = Path(temp_dir) / "chat.txt"
        file_path.write_text("[2024-03-01 18:30] Me: Hello\nAlex: Hi\n", encoding="utf-8")

        conversation = ParserFactory.parse_file(file_path, self_names=["Me"])

    assert conversation.conversation_id == "chat"
    assert conversation.source_kind == ConversationSourceKind.TEXT_EXPORT
    assert conversation.message_count == 2


def test_parser_factory_rejects_unsupported_extensions() -> None:
    """It raises a clear error for unsupported transcript types."""

    try:
        ParserFactory.create_parser("chat.json")
    except ValueError as error:
        assert ".json" in str(error)
        return

    raise AssertionError("Expected ValueError for unsupported extension")
