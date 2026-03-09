"""Lightweight conversation normalization helpers.

This module applies a small, auditable cleanup pass on parsed conversations
before analysis begins. The normalization stays intentionally conservative for
the MVP: it cleans message text, deduplicates participant aliases, fills a
title when one is missing, and backfills a few metadata fields that later
pipeline stages can rely on.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.parsers.schema import (
    Conversation,
    ConversationParticipant,
    Message,
    MessageRole,
)


_CJK_CHARACTER_PATTERN = re.compile(r"[\u3400-\u9fff]")
_NON_WORD_PATTERN = re.compile(r"[^0-9a-zA-Z\u4e00-\u9fff]+")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_ZERO_WIDTH_PATTERN = re.compile(r"[\u200b\u200c\u200d\ufeff]")


class ConversationNormalizer:
    """Apply a small normalization pass to parsed conversations."""

    normalizer_name = "conversation_normalizer"
    normalizer_version = "0.1.0"

    def normalize(
        self,
        conversation: Conversation,
        *,
        default_timezone: str | None = None,
        default_language: str | None = None,
    ) -> Conversation:
        """Return a cleaned conversation ready for downstream analyzers."""

        message_copies = [message.copy(deep=True) for message in conversation.messages]
        participant_copies = self._collect_participants(conversation, message_copies)
        canonical_participants, participant_id_map = self._canonicalize_participants(
            participant_copies
        )
        normalized_messages = self._normalize_messages(
            messages=message_copies,
            participants=canonical_participants,
            participant_id_map=participant_id_map,
        )

        title = self._resolve_title(
            conversation=conversation,
            participants=canonical_participants,
        )
        language = (
            conversation.language
            or default_language
            or self._infer_language(normalized_messages)
        )
        timezone = conversation.timezone or default_timezone
        metadata = self._build_metadata(
            conversation=conversation,
            participants=canonical_participants,
            messages=normalized_messages,
        )

        return Conversation(
            conversation_id=conversation.conversation_id,
            title=title,
            source_kind=conversation.source_kind,
            participants=canonical_participants,
            messages=normalized_messages,
            timezone=timezone,
            language=language,
            parser_warnings=list(conversation.parser_warnings),
            metadata=metadata,
        )

    def _collect_participants(
        self,
        conversation: Conversation,
        messages: list[Message],
    ) -> list[ConversationParticipant]:
        """Build a participant list that also covers message-only speakers."""

        participants: dict[str, ConversationParticipant] = {
            participant.participant_id: participant.copy(deep=True)
            for participant in conversation.participants
        }
        for message in messages:
            speaker_id = message.speaker_id or self._fallback_participant_id(message)
            if speaker_id is None:
                continue

            participant = participants.get(speaker_id)
            if participant is None:
                aliases = [message.speaker_name] if message.speaker_name else []
                participants[speaker_id] = ConversationParticipant(
                    participant_id=speaker_id,
                    display_name=message.speaker_name,
                    role=message.speaker_role,
                    aliases=aliases,
                )
                continue

            if participant.display_name is None and message.speaker_name:
                participant.display_name = message.speaker_name
            if message.speaker_name:
                participant.aliases.append(message.speaker_name)
            if (
                participant.role == MessageRole.UNKNOWN
                and message.speaker_role != MessageRole.UNKNOWN
            ):
                participant.role = message.speaker_role

        return list(participants.values())

    def _canonicalize_participants(
        self,
        participants: list[ConversationParticipant],
    ) -> tuple[list[ConversationParticipant], dict[str, str]]:
        """Merge obviously duplicated participants and deduplicate aliases."""

        grouped: dict[str, list[ConversationParticipant]] = {}
        for participant in participants:
            grouping_key = self._participant_group_key(participant)
            grouped.setdefault(grouping_key, []).append(participant)

        canonical_participants: list[ConversationParticipant] = []
        participant_id_map: dict[str, str] = {}

        for group in grouped.values():
            canonical = group[0].copy(deep=True)
            alias_candidates: list[str] = []
            explicit_roles = [item.role for item in group if item.role != MessageRole.UNKNOWN]

            for item in group:
                participant_id_map[item.participant_id] = canonical.participant_id
                if item.display_name:
                    alias_candidates.append(item.display_name)
                alias_candidates.extend(item.aliases)

            canonical.aliases = self._deduplicate_aliases(alias_candidates)
            if canonical.display_name is None and canonical.aliases:
                canonical.display_name = canonical.aliases[0]
            if explicit_roles:
                canonical.role = explicit_roles[0]
            canonical_participants.append(canonical)

        human_participants = [
            participant
            for participant in canonical_participants
            if participant.role not in {MessageRole.SELF, MessageRole.SYSTEM}
        ]
        if len(human_participants) == 1 and human_participants[0].role == MessageRole.UNKNOWN:
            human_participants[0].role = MessageRole.OTHER

        return canonical_participants, participant_id_map

    def _normalize_messages(
        self,
        *,
        messages: list[Message],
        participants: list[ConversationParticipant],
        participant_id_map: dict[str, str],
    ) -> list[Message]:
        """Clean message text and align speaker fields with canonical participants."""

        participants_by_id = {
            participant.participant_id: participant for participant in participants
        }
        normalized_messages: list[Message] = []

        for message in messages:
            original_speaker_id = message.speaker_id or self._fallback_participant_id(message)
            canonical_speaker_id = (
                participant_id_map.get(original_speaker_id)
                if original_speaker_id is not None
                else None
            )
            canonical_participant = (
                participants_by_id.get(canonical_speaker_id)
                if canonical_speaker_id is not None
                else None
            )

            cleaned_text = self._clean_text(message.text)
            cleaned_normalized_text = self._clean_text(message.normalized_text or cleaned_text)
            metadata = dict(message.metadata)
            metadata["normalized"] = True
            if cleaned_text != message.text:
                metadata["text_cleaned"] = True

            normalized_messages.append(
                message.copy(
                    update={
                        "speaker_id": canonical_speaker_id,
                        "speaker_name": (
                            canonical_participant.display_name
                            if canonical_participant is not None
                            else self._clean_text(message.speaker_name)
                        ),
                        "speaker_role": (
                            canonical_participant.role
                            if canonical_participant is not None
                            else message.speaker_role
                        ),
                        "text": cleaned_text,
                        "normalized_text": cleaned_normalized_text,
                        "metadata": metadata,
                    },
                    deep=True,
                )
            )

        return normalized_messages

    def _resolve_title(
        self,
        *,
        conversation: Conversation,
        participants: list[ConversationParticipant],
    ) -> str:
        """Return the existing title or a lightweight fallback title."""

        cleaned_title = self._clean_text(conversation.title)
        if cleaned_title:
            return cleaned_title

        source_ref = self._conversation_source_ref(conversation)
        if source_ref:
            return (
                Path(source_ref).stem.replace("_", " ").strip().title()
                or "Imported Conversation"
            )

        other_participant = next(
            (
                participant
                for participant in participants
                if participant.role in {MessageRole.OTHER, MessageRole.UNKNOWN}
                and participant.display_name
            ),
            None,
        )
        if other_participant is not None:
            return f"Conversation with {other_participant.display_name}"

        return "Imported Conversation"

    def _build_metadata(
        self,
        *,
        conversation: Conversation,
        participants: list[ConversationParticipant],
        messages: list[Message],
    ) -> dict[str, object]:
        """Backfill small conversation-level metadata used by later stages."""

        role_counts: dict[str, int] = {}
        for participant in participants:
            role_counts[participant.role.value] = role_counts.get(participant.role.value, 0) + 1

        metadata: dict[str, object] = dict(conversation.metadata)
        metadata.update(
            {
                "source_ref": self._conversation_source_ref(conversation),
                "normalizer_name": self.normalizer_name,
                "normalizer_version": self.normalizer_version,
                "participant_count": len(participants),
                "message_count": len(messages),
                "has_timestamps": any(message.sent_at is not None for message in messages),
                "missing_timestamps": sum(message.sent_at is None for message in messages),
                "participant_roles": role_counts,
                "title_was_inferred": conversation.title is None,
            }
        )
        return metadata

    def _conversation_source_ref(self, conversation: Conversation) -> str | None:
        """Return the first available source reference for the conversation."""

        metadata_source_ref = conversation.metadata.get("source_ref")
        if isinstance(metadata_source_ref, str) and metadata_source_ref.strip():
            return metadata_source_ref.strip()

        for message in conversation.messages:
            if message.provenance and message.provenance.source_ref:
                return message.provenance.source_ref
        return None

    def _infer_language(self, messages: list[Message]) -> str:
        """Infer a coarse language hint from normalized message text."""

        joined_text = " ".join(
            message.normalized_text or ""
            for message in messages
            if message.normalized_text is not None
        )
        if not joined_text:
            return "zh-CN"

        cjk_count = len(_CJK_CHARACTER_PATTERN.findall(joined_text))
        if cjk_count >= max(4, len(joined_text) // 8):
            return "zh-CN"
        return "en-US"

    def _participant_group_key(self, participant: ConversationParticipant) -> str:
        """Build a conservative grouping key for participant deduplication."""

        if participant.role == MessageRole.SELF:
            return "self"
        if participant.role == MessageRole.SYSTEM:
            return f"system:{participant.participant_id}"

        alias_seed = participant.display_name or (
            participant.aliases[0] if participant.aliases else participant.participant_id
        )
        return f"human:{self._normalize_person_key(alias_seed)}"

    def _fallback_participant_id(self, message: Message) -> str | None:
        """Build a lightweight participant id from the message speaker fields."""

        if message.speaker_name is None:
            return None

        normalized = self._normalize_person_key(message.speaker_name)
        return normalized or None

    def _normalize_person_key(self, value: str) -> str:
        """Normalize one speaker label into a conservative comparison key."""

        slug = _NON_WORD_PATTERN.sub("_", value.strip()).strip("_")
        return slug.casefold()

    def _deduplicate_aliases(self, aliases: list[str]) -> list[str]:
        """Deduplicate aliases while preserving their first meaningful spelling."""

        deduplicated: list[str] = []
        seen: set[str] = set()
        for alias in aliases:
            cleaned_alias = self._clean_text(alias)
            if not cleaned_alias:
                continue
            alias_key = cleaned_alias.casefold()
            if alias_key in seen:
                continue
            deduplicated.append(cleaned_alias)
            seen.add(alias_key)
        return deduplicated

    def _clean_text(self, value: str | None) -> str | None:
        """Remove zero-width characters and collapse extra whitespace."""

        if value is None:
            return None

        without_zero_width = _ZERO_WIDTH_PATTERN.sub("", value)
        collapsed = _WHITESPACE_PATTERN.sub(" ", without_zero_width).strip()
        return collapsed or None


__all__ = ["ConversationNormalizer"]
