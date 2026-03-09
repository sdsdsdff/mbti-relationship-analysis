"""Plain text conversation parser for simple chat transcript imports.

This MVP parser handles line-oriented text transcripts with one message per
line. It supports two lightweight formats that are easy to hand-edit or export
from simple notes:

- `[2024-01-01 09:00] Alice: Hello`
- `Bob: Hi there`

Malformed lines are skipped and recorded as parser warnings instead of aborting
the whole import.
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

_TEXT_MESSAGE_PATTERNS = (
    re.compile(
        r"^\[(?P<timestamp>[^\]]+)\]\s+(?P<speaker>[^:：]+)[:：]\s*(?P<text>.+?)\s*$"
    ),
    re.compile(r"^(?P<speaker>[^:：]+)[:：]\s*(?P<text>.+?)\s*$"),
)


class TextParser:
    """Parse simple line-based text chat transcripts into the normalized schema."""

    parser_name = "text_parser"

    def __init__(self, self_names: Iterable[str] | None = None) -> None:
        """Store optional aliases used to tag the self participant."""

        normalized_names = self_names or []
        self._self_names = {
            name.strip().casefold() for name in normalized_names if name.strip()
        }

    def parse_file(self, path: str | Path) -> Conversation:
        """Parse one text transcript file into a conversation."""

        file_path = Path(path)
        return self.parse_text(file_path.read_text(encoding="utf-8"), source_ref=file_path.name)

    def parse_text(self, content: str, *, source_ref: str | None = None) -> Conversation:
        """Parse text transcript content into a normalized conversation."""

        warnings: list[str] = []
        participants: dict[str, ConversationParticipant] = {}
        messages: list[Message] = []

        for line_number, raw_line in enumerate(content.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue

            matched = _match_message_line(line)
            if not matched:
                warnings.append(f"Skipped unsupported text line {line_number}: {line}")
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
                    sent_at=_parse_timestamp(matched.groupdict().get("timestamp")),
                    provenance=ParserProvenance(
                        source_kind=ConversationSourceKind.TEXT_EXPORT,
                        source_ref=source_ref,
                        parser_name=self.parser_name,
                        parse_confidence=1.0,
                        raw_metadata={"line_number": line_number, "format": "plain_text"},
                    ),
                )
            )

        conversation_id = _build_conversation_id(source_ref=source_ref, fallback="text")
        return Conversation(
            conversation_id=conversation_id,
            source_kind=ConversationSourceKind.TEXT_EXPORT,
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


def _match_message_line(line: str) -> re.Match[str] | None:
    """Match one supported text message format."""

    for pattern in _TEXT_MESSAGE_PATTERNS:
        matched = pattern.match(line)
        if matched:
            return matched
    return None


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
