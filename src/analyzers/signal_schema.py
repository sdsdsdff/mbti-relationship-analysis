"""Behavior signal schemas used between parsing and report generation.

This module defines the project's intermediate evidence layer: small, typed
behavioral signals extracted from normalized conversations. A signal is not a
final personality or relationship conclusion. Instead, it captures one observed
interaction pattern together with its evidence, strength, and confidence so the
later report layer can stay explainable and auditable.

Design goals:

- keep signals local and evidence-driven rather than jumping to global labels;
- separate signal strength from extractor confidence;
- support signals about `我`、`TA` or the dyad itself;
- preserve message anchors for later evidence review.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, root_validator, validator


class SignalSubject(str, Enum):
    """Who the signal is primarily describing."""

    SELF = "self"
    OTHER = "other"
    DYAD = "dyad"


class SignalEvidenceSource(str, Enum):
    """Whether a signal comes from chat evidence or user-provided context."""

    CHAT_RECORD = "chat_record"
    USER_BACKGROUND = "user_background"
    MIXED = "mixed"


class SignalValence(str, Enum):
    """Coarse interpretation direction for a behavior signal."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    NEUTRAL = "neutral"


class BehaviorSignalCategory(str, Enum):
    """High-level bucket for a behavior signal."""

    CONVERSATION_FLOW = "conversation_flow"
    EMOTIONAL_EXPRESSION = "emotional_expression"
    RELATIONAL_BOUNDARY = "relational_boundary"
    CONFLICT_AND_REPAIR = "conflict_and_repair"
    COORDINATION = "coordination"


class BehaviorSignalType(str, Enum):
    """Signal types that are practical to extract from chat behavior."""

    INITIATIVE = "initiative"
    RESPONSIVENESS = "responsiveness"
    SELF_DISCLOSURE = "self_disclosure"
    EMOTIONAL_WARMTH = "emotional_warmth"
    VALIDATION = "validation"
    CURIOSITY = "curiosity"
    BOUNDARY_SETTING = "boundary_setting"
    WITHDRAWAL = "withdrawal"
    CONFLICT_ESCALATION = "conflict_escalation"
    REPAIR_ATTEMPT = "repair_attempt"
    PLANNING_ORIENTATION = "planning_orientation"
    FOLLOW_THROUGH = "follow_through"
    AMBIGUITY_MANAGEMENT = "ambiguity_management"


class SignalStrengthBand(str, Enum):
    """Human-readable band for signal intensity."""

    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class ConfidenceBand(str, Enum):
    """Human-readable band for extractor confidence."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


_CATEGORY_BY_SIGNAL_TYPE: dict[BehaviorSignalType, BehaviorSignalCategory] = {
    BehaviorSignalType.INITIATIVE: BehaviorSignalCategory.CONVERSATION_FLOW,
    BehaviorSignalType.RESPONSIVENESS: BehaviorSignalCategory.CONVERSATION_FLOW,
    BehaviorSignalType.SELF_DISCLOSURE: BehaviorSignalCategory.EMOTIONAL_EXPRESSION,
    BehaviorSignalType.EMOTIONAL_WARMTH: BehaviorSignalCategory.EMOTIONAL_EXPRESSION,
    BehaviorSignalType.VALIDATION: BehaviorSignalCategory.EMOTIONAL_EXPRESSION,
    BehaviorSignalType.CURIOSITY: BehaviorSignalCategory.EMOTIONAL_EXPRESSION,
    BehaviorSignalType.BOUNDARY_SETTING: BehaviorSignalCategory.RELATIONAL_BOUNDARY,
    BehaviorSignalType.WITHDRAWAL: BehaviorSignalCategory.RELATIONAL_BOUNDARY,
    BehaviorSignalType.CONFLICT_ESCALATION: BehaviorSignalCategory.CONFLICT_AND_REPAIR,
    BehaviorSignalType.REPAIR_ATTEMPT: BehaviorSignalCategory.CONFLICT_AND_REPAIR,
    BehaviorSignalType.PLANNING_ORIENTATION: BehaviorSignalCategory.COORDINATION,
    BehaviorSignalType.FOLLOW_THROUGH: BehaviorSignalCategory.COORDINATION,
    BehaviorSignalType.AMBIGUITY_MANAGEMENT: BehaviorSignalCategory.COORDINATION,
}


def _strength_band(score: float) -> SignalStrengthBand:
    """Convert a numeric intensity score into a readable band."""

    if score < 0.34:
        return SignalStrengthBand.WEAK
    if score < 0.67:
        return SignalStrengthBand.MODERATE
    return SignalStrengthBand.STRONG


def _confidence_band(score: float) -> ConfidenceBand:
    """Convert a numeric confidence score into a readable band."""

    if score < 0.45:
        return ConfidenceBand.LOW
    if score < 0.75:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.HIGH


class SignalStrength(BaseModel):
    """Normalized signal intensity independent from extractor confidence."""

    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="How strongly the pattern appears in evidence.",
    )
    band: SignalStrengthBand | None = Field(
        default=None,
        description="Human-readable intensity band derived from the numeric score.",
    )

    @validator("band", always=True)
    def infer_band(cls, band: SignalStrengthBand | None, values: dict[str, Any]) -> SignalStrengthBand:
        """Backfill the band from the numeric score when omitted."""

        if band is not None:
            return band
        return _strength_band(values["score"])


class SignalConfidence(BaseModel):
    """Confidence assigned to the signal extraction result."""

    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="How trustworthy the extraction is given the available evidence.",
    )
    band: ConfidenceBand | None = Field(
        default=None,
        description="Human-readable confidence band derived from the numeric score.",
    )
    rationale: str | None = Field(
        default=None,
        description="Optional short explanation for why confidence is limited or high.",
    )

    @validator("band", always=True)
    def infer_band(cls, band: ConfidenceBand | None, values: dict[str, Any]) -> ConfidenceBand:
        """Backfill the band from the numeric score when omitted."""

        if band is not None:
            return band
        return _confidence_band(values["score"])


class InteractionWindow(BaseModel):
    """Optional message/timestamp span supporting one extracted signal."""

    start_message_id: str | None = Field(default=None, description="First related message id.")
    end_message_id: str | None = Field(default=None, description="Last related message id.")
    start_time: datetime | None = Field(default=None, description="First related timestamp.")
    end_time: datetime | None = Field(default=None, description="Last related timestamp.")


class BehaviorSignal(BaseModel):
    """One evidence-backed interaction pattern extracted from a conversation."""

    signal_id: str = Field(..., description="Stable identifier for the extracted signal.")
    type: BehaviorSignalType = Field(..., description="Concrete behavior signal type.")
    category: BehaviorSignalCategory | None = Field(
        default=None,
        description="High-level category; inferred from type when omitted.",
    )
    subject: SignalSubject = Field(..., description="Who the signal primarily describes.")
    participant_id: str | None = Field(
        default=None,
        description="Conversation participant id when the signal targets a specific person.",
    )
    summary: str = Field(..., description="Short natural-language description of the pattern.")
    strength: SignalStrength = Field(..., description="Observed strength of the pattern.")
    confidence: SignalConfidence = Field(
        ..., description="Trust level for the extraction result."
    )
    valence: SignalValence = Field(
        default=SignalValence.NEUTRAL,
        description="Coarse interpretation direction for later report rendering.",
    )
    evidence_source: SignalEvidenceSource = Field(
        default=SignalEvidenceSource.CHAT_RECORD,
        description="Whether evidence comes from chat logs, user background, or both.",
    )
    message_ids: list[str] = Field(
        default_factory=list,
        description="Supporting normalized message identifiers.",
    )
    counter_message_ids: list[str] = Field(
        default_factory=list,
        description="Optional counter-evidence message identifiers.",
    )
    window: InteractionWindow | None = Field(
        default=None,
        description="Optional message or time span for the observed pattern.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Short caveats or extraction notes for review.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extractor-specific details that do not belong in core fields.",
    )

    class Config:
        anystr_strip_whitespace = True

    @validator("category", always=True)
    def infer_category(
        cls, category: BehaviorSignalCategory | None, values: dict[str, Any]
    ) -> BehaviorSignalCategory:
        """Backfill the category from the signal type when omitted."""

        expected_category = _CATEGORY_BY_SIGNAL_TYPE[values["type"]]
        if category is not None:
            if category != expected_category:
                raise ValueError("category does not match the provided signal type")
            return category
        return expected_category

    @root_validator
    def validate_subject_and_evidence(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Keep the signal anchored to at least one evidence source."""

        message_ids = values.get("message_ids") or []
        evidence_source = values.get("evidence_source")
        subject = values.get("subject")

        if evidence_source == SignalEvidenceSource.CHAT_RECORD and not message_ids:
            raise ValueError("chat_record signals must reference at least one message_id")

        if subject == SignalSubject.DYAD and values.get("participant_id") is not None:
            raise ValueError("dyad signals should not set participant_id")

        return values


class BehaviorSignalSet(BaseModel):
    """Collection of extracted signals for one normalized conversation."""

    signal_set_id: str = Field(..., description="Stable identifier for one extraction run.")
    conversation_id: str = Field(..., description="Associated normalized conversation id.")
    extractor_name: str = Field(..., description="Signal extractor component or pipeline name.")
    extractor_version: str | None = Field(
        default=None,
        description="Version string for reproducibility.",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when the signal set was produced.",
    )
    signals: list[BehaviorSignal] = Field(
        default_factory=list,
        description="Behavior signals extracted for this conversation.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extraction-scoped metadata and diagnostics.",
    )

    @validator("signals")
    def ensure_unique_signal_ids(cls, signals: list[BehaviorSignal]) -> list[BehaviorSignal]:
        """Reject duplicate signal identifiers inside one signal set."""

        signal_ids = [signal.signal_id for signal in signals]
        if len(signal_ids) != len(set(signal_ids)):
            raise ValueError("signal_id values must be unique within a signal set")
        return signals


__all__ = [
    "BehaviorSignal",
    "BehaviorSignalCategory",
    "BehaviorSignalSet",
    "BehaviorSignalType",
    "ConfidenceBand",
    "InteractionWindow",
    "SignalConfidence",
    "SignalEvidenceSource",
    "SignalStrength",
    "SignalStrengthBand",
    "SignalSubject",
    "SignalValence",
]
