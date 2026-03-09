"""Prompt packaging helpers for the MVP BYOK analysis flow.

The prompt layer converts normalized conversations and heuristic signals into a
compact, provider-agnostic chat payload. The wording stays deliberately
conservative: the model is asked to remain evidence-based, surface
uncertainties, and avoid deterministic MBTI or relationship claims.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Mapping

from pydantic import BaseModel, Field

from src.analyzers.signal_schema import BehaviorSignalSet
from src.parsers.schema import Conversation


class LLMMessageRole(str, Enum):
    """Supported chat roles for provider-agnostic prompt bundles."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class LLMMessage(BaseModel):
    """One normalized chat message ready for an external LLM API."""

    role: LLMMessageRole = Field(..., description="Chat role for the message.")
    content: str = Field(..., description="Plain-text content sent to the model.")

    class Config:
        anystr_strip_whitespace = True


class LLMResponseContract(BaseModel):
    """Minimal JSON contract requested from the external LLM."""

    format: str = Field(
        default="json_object",
        description="Expected top-level response shape requested from the model.",
    )
    required_fields: list[str] = Field(
        default_factory=lambda: [
            "summary",
            "type_assessments",
            "insights",
            "uncertainty_notes",
        ],
        description="Required keys expected in the model's JSON response.",
    )
    schema_hint: dict[str, Any] = Field(
        default_factory=lambda: {
            "summary": "string",
            "type_assessments": [
                {
                    "subject": "self|other",
                    "summary": "string",
                    "confidence": "0.0-1.0",
                    "signal_ids": ["signal_id"],
                    "candidates": [
                        {
                            "mbti_type": "ENFP",
                            "score": "0.0-1.0",
                            "why_like": ["string"],
                            "why_not_like": ["string"],
                        }
                    ],
                }
            ],
            "insights": [
                {
                    "section": "overview|self|other|relationship|advice",
                    "title": "string",
                    "summary": "string",
                    "bullets": ["string"],
                    "confidence": "0.0-1.0",
                    "signal_ids": ["signal_id"],
                }
            ],
            "uncertainty_notes": ["string"],
        },
        description="Compact structural hint for JSON output generation.",
    )


class LLMPromptBundle(BaseModel):
    """Provider-agnostic prompt bundle produced from local analysis artifacts."""

    system_prompt: str = Field(
        ...,
        description="System-level instruction string for the external model.",
    )
    messages: list[LLMMessage] = Field(
        ...,
        description="Ordered chat messages ready for provider payload builders.",
    )
    response_contract: LLMResponseContract = Field(
        default_factory=LLMResponseContract,
        description="Expected response contract requested from the LLM.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Trace metadata about the packaged prompt input.",
    )

    class Config:
        anystr_strip_whitespace = True


class LLMPromptPackager:
    """Build conservative JSON-oriented prompts for the MVP BYOK flow."""

    def build(
        self,
        conversation: Conversation,
        signal_set: BehaviorSignalSet,
        *,
        background_info: Mapping[str, Any] | None = None,
    ) -> LLMPromptBundle:
        """Package conversation evidence into a provider-agnostic prompt bundle."""

        background_payload = dict(background_info or {})
        analysis_context = {
            "conversation": self._serialize_conversation(conversation),
            "signals": self._serialize_signal_set(signal_set),
            "background_info": background_payload,
        }
        response_contract = LLMResponseContract()
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            analysis_context=analysis_context,
            response_contract=response_contract,
        )

        return LLMPromptBundle(
            system_prompt=system_prompt,
            messages=[
                LLMMessage(role=LLMMessageRole.SYSTEM, content=system_prompt),
                LLMMessage(role=LLMMessageRole.USER, content=user_prompt),
            ],
            response_contract=response_contract,
            metadata={
                "conversation_id": conversation.conversation_id,
                "signal_set_id": signal_set.signal_set_id,
                "message_count": conversation.message_count,
                "signal_count": len(signal_set.signals),
                "has_background_info": bool(background_payload),
            },
        )

    def _build_system_prompt(self) -> str:
        """Return the conservative system instruction used across providers."""

        return (
            "You are assisting an evidence-based relationship analysis workflow. "
            "Ground every conclusion in the supplied conversation evidence and "
            "heuristic signals. Explicitly surface uncertainty, sample-size limits, "
            "and counter-evidence when relevant. Avoid deterministic MBTI typing, "
            "avoid diagnostic language, and do not present relationship outcomes as "
            "fixed facts. Treat any MBTI hypothesis as tentative and revisable. "
            "Return only valid JSON matching the requested contract."
        )

    def _build_user_prompt(
        self,
        *,
        analysis_context: dict[str, Any],
        response_contract: LLMResponseContract,
    ) -> str:
        """Render the user message containing structured evidence and output rules."""

        context_json = json.dumps(analysis_context, ensure_ascii=False, indent=2)
        contract_json = json.dumps(response_contract.dict(), ensure_ascii=False, indent=2)
        return (
            "Please review the structured conversation evidence below and propose a "
            "cautious, uncertainty-aware JSON response. Keep claims tied to the given "
            "signals and messages. If evidence is insufficient, say so directly in the "
            "summary or uncertainty notes.\n\n"
            "<analysis_context>\n"
            f"{context_json}\n"
            "</analysis_context>\n\n"
            "<response_contract>\n"
            f"{contract_json}\n"
            "</response_contract>"
        )

    def _serialize_conversation(self, conversation: Conversation) -> dict[str, Any]:
        """Convert the normalized conversation into compact JSON-ready data."""

        return {
            "conversation_id": conversation.conversation_id,
            "title": conversation.title,
            "language": conversation.language,
            "timezone": conversation.timezone,
            "participants": [
                {
                    "participant_id": participant.participant_id,
                    "display_name": participant.display_name,
                    "role": participant.role.value,
                }
                for participant in conversation.participants
            ],
            "messages": [
                {
                    "message_id": message.message_id,
                    "sequence_no": message.sequence_no,
                    "speaker_id": message.speaker_id,
                    "speaker_name": message.speaker_name,
                    "speaker_role": message.speaker_role.value,
                    "sent_at": (
                        message.sent_at.isoformat()
                        if message.sent_at is not None
                        else None
                    ),
                    "text": message.normalized_text or message.text,
                }
                for message in conversation.messages
            ],
            "parser_warnings": list(conversation.parser_warnings),
        }

    def _serialize_signal_set(self, signal_set: BehaviorSignalSet) -> dict[str, Any]:
        """Convert heuristic signals into a compact JSON-ready evidence summary."""

        return {
            "signal_set_id": signal_set.signal_set_id,
            "extractor_name": signal_set.extractor_name,
            "extractor_version": signal_set.extractor_version,
            "signals": [
                {
                    "signal_id": signal.signal_id,
                    "type": signal.type.value,
                    "subject": signal.subject.value,
                    "summary": signal.summary,
                    "strength": signal.strength.score,
                    "confidence": signal.confidence.score,
                    "message_ids": list(signal.message_ids),
                    "notes": list(signal.notes),
                }
                for signal in signal_set.signals
            ],
        }


__all__ = [
    "LLMMessage",
    "LLMMessageRole",
    "LLMPromptBundle",
    "LLMPromptPackager",
    "LLMResponseContract",
]
