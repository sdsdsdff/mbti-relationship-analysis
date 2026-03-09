"""Internal normalized conversation schemas.

This module defines the first stable data layer used by the project after raw
chat exports or screenshots are parsed. The models are intentionally slim:
single messages only keep content, speaker, ordering, and provenance data;
analysis results such as personality guesses or behavioral interpretations live
in later pipeline stages.

The schema is designed around the product spec's input principles:

- support both text exports and screenshot/VLM reconstruction;
- normalize everything into one source-agnostic conversation format;
- preserve enough provenance for re-processing and evidence lookup;
- keep parser uncertainty separate from downstream analysis results.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, root_validator, validator


class ConversationSourceKind(str, Enum):
    """High-level source category for an imported conversation."""

    MARKDOWN = "markdown"
    TEXT_EXPORT = "text_export"
    SCREENSHOT = "screenshot"
    LONG_SCREENSHOT = "long_screenshot"
    MIXED = "mixed"


class MessageRole(str, Enum):
    """Normalized speaker role used across import formats."""

    SELF = "self"
    OTHER = "other"
    UNKNOWN = "unknown"
    SYSTEM = "system"


class MessageKind(str, Enum):
    """Canonical content kind for a normalized message."""

    TEXT = "text"
    IMAGE = "image"
    EMOJI = "emoji"
    STICKER = "sticker"
    AUDIO = "audio"
    VIDEO = "video"
    FILE = "file"
    CALL = "call"
    SYSTEM_NOTICE = "system_notice"


class AttachmentRef(BaseModel):
    """Lightweight attachment reference kept on a normalized message."""

    attachment_id: str = Field(..., description="Stable identifier within one import.")
    kind: MessageKind = Field(..., description="Attachment kind after normalization.")
    uri: str | None = Field(
        default=None,
        description="Local path, remote URL, or opaque storage identifier.",
    )
    mime_type: str | None = Field(default=None, description="Optional MIME type.")
    caption: str | None = Field(default=None, description="Optional attachment caption.")

    class Config:
        anystr_strip_whitespace = True


class ParserProvenance(BaseModel):
    """Traceability metadata describing how a message was recovered."""

    source_kind: ConversationSourceKind = Field(
        ..., description="Original import channel before normalization."
    )
    source_ref: str | None = Field(
        default=None,
        description="Filename, screenshot name, or other source identifier.",
    )
    parser_name: str | None = Field(
        default=None,
        description="Parser, OCR, or VLM component name used during import.",
    )
    parse_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence of the import-layer reconstruction only.",
    )
    raw_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific details kept for debugging or replay.",
    )


class ConversationParticipant(BaseModel):
    """Normalized participant definition for a conversation."""

    participant_id: str = Field(..., description="Stable identifier within one conversation.")
    display_name: str | None = Field(default=None, description="Best-effort display name.")
    role: MessageRole = Field(
        default=MessageRole.UNKNOWN,
        description="Whether the participant is self, the other person, or system.",
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Known alternate names seen in the raw import.",
    )

    class Config:
        anystr_strip_whitespace = True


class Message(BaseModel):
    """One normalized message unit used by later analysis stages."""

    message_id: str = Field(..., description="Stable message identifier within one import.")
    sequence_no: int = Field(..., ge=0, description="Order index after normalization.")
    speaker_id: str | None = Field(
        default=None,
        description="Conversation participant identifier, if available.",
    )
    speaker_name: str | None = Field(
        default=None,
        description="Best-effort display name recovered from the source.",
    )
    speaker_role: MessageRole = Field(
        default=MessageRole.UNKNOWN,
        description="Normalized role label for the speaker.",
    )
    kind: MessageKind = Field(
        default=MessageKind.TEXT,
        description="Normalized message content type.",
    )
    text: str | None = Field(default=None, description="Recovered raw text payload.")
    normalized_text: str | None = Field(
        default=None,
        description="Whitespace-cleaned text used by downstream analyzers.",
    )
    sent_at: datetime | None = Field(
        default=None,
        description="Best-effort timestamp recovered from source records.",
    )
    reply_to_message_id: str | None = Field(
        default=None,
        description="Referenced parent message when the source exposes it.",
    )
    attachments: list[AttachmentRef] = Field(
        default_factory=list,
        description="Attachment references associated with the message.",
    )
    provenance: ParserProvenance | None = Field(
        default=None,
        description="Import-layer traceability metadata.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Small source-agnostic flags that do not fit dedicated fields.",
    )

    class Config:
        anystr_strip_whitespace = True

    @validator("normalized_text", always=True)
    def default_normalized_text(cls, value: str | None, values: dict[str, Any]) -> str | None:
        """Populate a normalized text view when raw text exists."""

        if value is not None:
            return value.strip() or None

        text = values.get("text")
        if text is None:
            return None

        normalized = " ".join(text.split())
        return normalized or None

    @root_validator
    def validate_content_presence(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Ensure the message carries at least one recoverable payload."""

        text = values.get("text")
        attachments = values.get("attachments") or []
        kind = values.get("kind")

        if not text and not attachments and kind not in {
            MessageKind.CALL,
            MessageKind.SYSTEM_NOTICE,
        }:
            raise ValueError("message must include text, attachments, or a non-text event kind")

        if values.get("speaker_role") == MessageRole.SYSTEM and values.get("speaker_id"):
            raise ValueError("system messages should not carry a participant speaker_id")

        return values


class Conversation(BaseModel):
    """A normalized conversation made of ordered messages and participants."""

    conversation_id: str = Field(..., description="Stable identifier for the normalized import.")
    title: str | None = Field(default=None, description="Optional conversation title.")
    source_kind: ConversationSourceKind = Field(
        ..., description="Primary import source category for the conversation."
    )
    participants: list[ConversationParticipant] = Field(
        default_factory=list,
        description="Known conversation participants after normalization.",
    )
    messages: list[Message] = Field(
        default_factory=list,
        description="Ordered normalized messages.",
    )
    timezone: str | None = Field(
        default=None,
        description="IANA timezone name when known from the source or user input.",
    )
    language: str | None = Field(
        default=None,
        description="Primary language code, for example zh-CN or en-US.",
    )
    started_at: datetime | None = Field(
        default=None,
        description="First message timestamp when available.",
    )
    ended_at: datetime | None = Field(
        default=None,
        description="Last message timestamp when available.",
    )
    parser_warnings: list[str] = Field(
        default_factory=list,
        description="Import-layer warnings such as OCR ambiguity or missing timestamps.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Conversation-scoped metadata kept outside dedicated fields.",
    )

    class Config:
        anystr_strip_whitespace = True

    @validator("participants")
    def ensure_unique_participants(
        cls, participants: list[ConversationParticipant]
    ) -> list[ConversationParticipant]:
        """Reject duplicated participant identifiers."""

        participant_ids = [participant.participant_id for participant in participants]
        if len(participant_ids) != len(set(participant_ids)):
            raise ValueError("participant_id values must be unique within a conversation")

        return participants

    @validator("messages")
    def ensure_unique_messages(cls, messages: list[Message]) -> list[Message]:
        """Reject duplicated message identifiers."""

        message_ids = [message.message_id for message in messages]
        if len(message_ids) != len(set(message_ids)):
            raise ValueError("message_id values must be unique within a conversation")

        sequence_numbers = [message.sequence_no for message in messages]
        if len(sequence_numbers) != len(set(sequence_numbers)):
            raise ValueError("sequence_no values must be unique within a conversation")

        return sorted(messages, key=lambda message: message.sequence_no)

    @root_validator
    def infer_time_bounds(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Backfill conversation start and end timestamps from message data."""

        messages = values.get("messages") or []
        timestamps = [message.sent_at for message in messages if message.sent_at is not None]
        if timestamps:
            if values.get("started_at") is None:
                values["started_at"] = min(timestamps)
            if values.get("ended_at") is None:
                values["ended_at"] = max(timestamps)

        return values

    @property
    def message_count(self) -> int:
        """Return the number of normalized messages."""

        return len(self.messages)


__all__ = [
    "AttachmentRef",
    "Conversation",
    "ConversationParticipant",
    "ConversationSourceKind",
    "Message",
    "MessageKind",
    "MessageRole",
    "ParserProvenance",
]
