"""Factory helpers for choosing the right conversation parser by file type.

The MVP keeps parser selection intentionally small: Markdown transcripts map to
the Markdown parser, and plain text transcripts map to the text parser. The
factory exposes a single import entrypoint so higher layers do not need to know
the concrete parser classes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.parsers.markdown_parser import MarkdownParser
from src.parsers.schema import Conversation
from src.parsers.text_parser import TextParser

SupportedParser = MarkdownParser | TextParser


class ParserFactory:
    """Create transcript parsers based on file extension."""

    _PARSER_TYPES = {
        ".md": MarkdownParser,
        ".markdown": MarkdownParser,
        ".txt": TextParser,
    }

    @classmethod
    def create_parser(
        cls,
        path: str | Path,
        *,
        self_names: Iterable[str] | None = None,
    ) -> SupportedParser:
        """Instantiate the parser that matches the given file extension."""

        extension = Path(path).suffix.casefold()
        parser_type = cls._PARSER_TYPES.get(extension)
        if parser_type is None:
            supported_extensions = ", ".join(sorted(cls._PARSER_TYPES))
            raise ValueError(
                f"Unsupported parser type '{extension or '<none>'}'. Supported: {supported_extensions}"
            )
        return parser_type(self_names=self_names)

    @classmethod
    def parse_file(
        cls,
        path: str | Path,
        *,
        self_names: Iterable[str] | None = None,
    ) -> Conversation:
        """Parse a transcript file with the parser selected from its suffix."""

        parser = cls.create_parser(path, self_names=self_names)
        return parser.parse_file(path)
