"""Markdown conversation parser for simple chat transcript imports.

This MVP parser handles lightweight Markdown exports where each chat message is
represented as a list item. The supported message patterns intentionally stay
small and predictable:

- `- [2024-01-01 09:00] Alice: Hello`
- `* Bob: Hi there`

Markdown headings are treated as the conversation title when present. Unknown
or malformed lines are skipped and recorded as parser warnings so later stages
can inspect import quality without breaking the whole import.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from typing import Iterable

from src.parsers.schema import (
    Conversation,
    ConversationParticipant,
    ConversationSourceKind,
    Message,
    MessageRole,
    ParserProvenance,
)

_MARKDOWN_MESSAGE_PATTERN = re.compile(
    r"^[-*]\s+(?:\[(?P<timestamp>[^\]]+)\]\s+)?(?P<speaker>[^:：]+)[:：]\s+(?P<text>.+?)\s*$"
)


class MarkdownParser:
    """Parse simple Markdown chat transcripts into the normalized schema."""

    parser_name = "markdown_parser"

    def __init__(self, self_names: Iterable[str] | None = None) -> None:
        """Store optional aliases used to tag the self participant."""

        normalized_names = self_names or []
        self._self_names = {
            name.strip().casefold() for name in normalized_names if name.strip()
        }

    def parse_file(self, path: str | Path) -> Conversation:
        """Parse one Markdown transcript file into a conversation."""

        file_path = Path(path)
        return self.parse_text(file_path.read_text(encoding="utf-8"), source_ref=file_path.name)

    def parse_text(self, content: str, *, source_ref: str | None = None) -> Conversation:
        """Parse Markdown transcript content into a normalized conversation."""

        title: str | None = None
        warnings: list[str] = []
        participants: dict[str, ConversationParticipant] = {}
        messages: list[Message] = []

        for line_number, raw_line in enumerate(content.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue

            if title is None and line.startswith("#"):
                title = line.lstrip("#").strip() or None
                continue

            matched = _MARKDOWN_MESSAGE_PATTERN.match(line)
            if not matched:
                warnings.append(f"Skipped unsupported markdown line {line_number}: {line}")
                continue

            speaker_name = matched.group("speaker").strip()
            speaker_id = _slugify_speaker_name(speaker_name)
            role = self._infer_role(speaker_name)
            participant = participants.setdefault(
                speaker_id,
                ConversationParticipant(
                    participant_id=speaker_id,
                    display_name=speaker_name,
                    role=role,
                    aliases=[speaker_name],
                ),
            )
            if participant.role != role and role != MessageRole.UNKNOWN:
                participant.role = role

            sequence_no = len(messages)
            messages.append(
                Message(
                    message_id=f"msg_{sequence_no}",
                    sequence_no=sequence_no,
                    speaker_id=speaker_id,
                    speaker_name=speaker_name,
                    speaker_role=participant.role,
                    text=matched.group("text").strip(),
                    sent_at=_parse_timestamp(matched.group("timestamp")),
                    provenance=ParserProvenance(
                        source_kind=ConversationSourceKind.MARKDOWN,
                        source_ref=source_ref,
                        parser_name=self.parser_name,
                        parse_confidence=1.0,
                        raw_metadata={"line_number": line_number, "format": "markdown_list"},
                    ),
                )
            )

        conversation_id = _build_conversation_id(source_ref=source_ref, fallback="markdown")
        return Conversation(
            conversation_id=conversation_id,
            title=title,
            source_kind=ConversationSourceKind.MARKDOWN,
            participants=list(participants.values()),
            messages=messages,
            parser_warnings=warnings,
            metadata={"parser_name": self.parser_name},
        )

    def _infer_role(self, speaker_name: str) -> MessageRole:
        """Infer the normalized speaker role from optional self aliases."""

        if speaker_name.strip().casefold() in self._self_names:
            return MessageRole.SELF
        return MessageRole.UNKNOWN


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse a small set of common timestamp formats for MVP imports."""

    if value is None:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    supported_formats = (
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
    )
    for timestamp_format in supported_formats:
        try:
            return datetime.strptime(normalized, timestamp_format)
        except ValueError:
            continue
    return None


def _slugify_speaker_name(value: str) -> str:
    """Build a stable participant identifier from a speaker label."""

    slug = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "_", value.strip()).strip("_")
    return slug.casefold() or "unknown_speaker"


def _build_conversation_id(*, source_ref: str | None, fallback: str) -> str:
    """Build a stable conversation identifier from the source name when available."""

    if source_ref:
        return Path(source_ref).stem or fallback
    return fallback
