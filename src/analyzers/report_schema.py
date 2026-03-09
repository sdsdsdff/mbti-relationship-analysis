"""Card-based report IR schemas.

This module defines the structured report layer consumed by renderers and other
application code after behavior signals have been aggregated into higher-level
findings. The schema follows the product spec's output design:

- reports are organized into `我` / `TA` / `我们` sections;
- the first layer stays simple and card-based for easy reading;
- important judgments carry explicit evidence anchors;
- chat evidence and user-supplied background remain distinguishable.

The resulting IR is intentionally presentation-friendly without mixing in view
framework concerns.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, root_validator, validator


class ReportSection(str, Enum):
    """Top-level report grouping aligned with the product's three-layer output."""

    SELF = "self"
    OTHER = "other"
    RELATIONSHIP = "relationship"


class ReportCardType(str, Enum):
    """Supported card types for the report's first and second layers."""

    LIKELY_TYPE = "likely_type"
    TYPE_CANDIDATES = "type_candidates"
    CURRENT_STAGE = "current_stage"
    STRENGTHS = "strengths"
    BLIND_SPOTS = "blind_spots"
    GROWTH_ADVICE = "growth_advice"
    RELATIONSHIP_DYNAMIC = "relationship_dynamic"
    COMMUNICATION_ADVICE = "communication_advice"
    EVIDENCE_REVIEW = "evidence_review"
    UNCERTAINTY = "uncertainty"


class ReportPriority(str, Enum):
    """Lightweight priority flag for downstream rendering."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    DETAIL = "detail"


class EvidenceSourceType(str, Enum):
    """Origin of an evidence anchor used in the final report."""

    CHAT_MESSAGE = "chat_message"
    USER_BACKGROUND = "user_background"
    DERIVED_SIGNAL = "derived_signal"


class TypeCandidate(BaseModel):
    """One MBTI candidate used by likely-type and candidate cards."""

    mbti_type: str = Field(..., description="Four-letter MBTI candidate type.")
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Relative fit score for the candidate type.",
    )
    why_like: list[str] = Field(
        default_factory=list,
        description="Short reasons supporting this candidate type.",
    )
    why_not_like: list[str] = Field(
        default_factory=list,
        description="Short counter-points or uncertainties for this candidate.",
    )

    class Config:
        anystr_strip_whitespace = True

    @validator("mbti_type")
    def validate_mbti_type(cls, value: str) -> str:
        """Require canonical four-letter MBTI codes."""

        normalized = value.upper()
        if re.fullmatch(r"[IE][NS][FT][JP]", normalized) is None:
            raise ValueError("mbti_type must be a canonical four-letter MBTI code")
        return normalized


class EvidenceAnchor(BaseModel):
    """Traceable evidence item attached to a report card."""

    anchor_id: str = Field(..., description="Stable identifier for the evidence anchor.")
    source_type: EvidenceSourceType = Field(..., description="Where the evidence comes from.")
    source_ref: str | None = Field(
        default=None,
        description="Form field key, derived signal id, or other external reference.",
    )
    message_ids: list[str] = Field(
        default_factory=list,
        description="Supporting normalized message ids when chat evidence is used.",
    )
    excerpt: str | None = Field(
        default=None,
        description="Short evidence excerpt suitable for UI display.",
    )
    summary: str = Field(
        ...,
        description="Why this evidence matters for the attached conclusion.",
    )
    signal_ids: list[str] = Field(
        default_factory=list,
        description="Behavior signal ids referenced by the anchor.",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence of the evidence-to-claim link when available.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Small UI or tracing hints outside the core schema.",
    )

    class Config:
        anystr_strip_whitespace = True

    @root_validator
    def validate_source_requirements(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Ensure each anchor keeps enough traceability for its source kind."""

        source_type = values.get("source_type")
        message_ids = values.get("message_ids") or []
        signal_ids = values.get("signal_ids") or []
        source_ref = values.get("source_ref")

        if source_type == EvidenceSourceType.CHAT_MESSAGE and not message_ids:
            raise ValueError("chat_message anchors must include at least one message_id")

        if source_type == EvidenceSourceType.USER_BACKGROUND and not source_ref:
            raise ValueError("user_background anchors must include a source_ref")

        if source_type == EvidenceSourceType.DERIVED_SIGNAL and not signal_ids and not source_ref:
            raise ValueError("derived_signal anchors must include signal_ids or source_ref")

        return values


class ReportCard(BaseModel):
    """Presentation-friendly unit that renders one finding or suggestion."""

    card_id: str = Field(..., description="Stable identifier for one report card.")
    section: ReportSection = Field(..., description="Which top-level section owns the card.")
    type: ReportCardType = Field(..., description="Report card type.")
    title: str = Field(..., description="Short display title for the card.")
    summary: str = Field(..., description="One-paragraph card summary.")
    bullets: list[str] = Field(
        default_factory=list,
        description="Short supporting bullets for the card body.",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence of the card-level conclusion when available.",
    )
    priority: ReportPriority = Field(
        default=ReportPriority.PRIMARY,
        description="Relative card prominence for UI rendering.",
    )
    candidates: list[TypeCandidate] = Field(
        default_factory=list,
        description="Optional MBTI candidates referenced by this card.",
    )
    signal_ids: list[str] = Field(
        default_factory=list,
        description="Behavior signal ids used to form the card.",
    )
    evidence: list[EvidenceAnchor] = Field(
        default_factory=list,
        description="Evidence anchors attached directly to the card.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Optional lightweight labels for filtering or styling.",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Card-specific structured payload kept outside the core fields.",
    )

    class Config:
        anystr_strip_whitespace = True

    @root_validator
    def validate_card_shape(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Apply a few minimal structural checks for key card types."""

        card_type = values.get("type")
        candidates = values.get("candidates") or []
        evidence = values.get("evidence") or []

        if card_type in {ReportCardType.LIKELY_TYPE, ReportCardType.TYPE_CANDIDATES} and not candidates:
            raise ValueError("type cards must include at least one candidate")

        anchor_ids = [anchor.anchor_id for anchor in evidence]
        if len(anchor_ids) != len(set(anchor_ids)):
            raise ValueError("anchor_id values must be unique within a card")

        return values


class ReportSectionBlock(BaseModel):
    """Group of cards belonging to one of the three main report sections."""

    section: ReportSection = Field(..., description="Section identifier.")
    headline: str = Field(..., description="Short headline for the section.")
    summary: str | None = Field(default=None, description="Optional section-level summary.")
    cards: list[ReportCard] = Field(
        default_factory=list,
        description="Cards rendered under this section.",
    )

    class Config:
        anystr_strip_whitespace = True

    @validator("cards")
    def ensure_cards_match_section(cls, cards: list[ReportCard], values: dict[str, Any]) -> list[ReportCard]:
        """Keep each card aligned with its section block."""

        section = values.get("section")
        for card in cards:
            if section is not None and card.section != section:
                raise ValueError("card.section must match the enclosing section block")

        card_ids = [card.card_id for card in cards]
        if len(card_ids) != len(set(card_ids)):
            raise ValueError("card_id values must be unique within a section")

        return cards


class AnalysisReportIR(BaseModel):
    """Top-level intermediate representation for one generated analysis report."""

    report_id: str = Field(..., description="Stable identifier for one generated report.")
    conversation_id: str = Field(..., description="Associated normalized conversation id.")
    schema_version: str = Field(
        default="1.0.0",
        description="Version of the report IR schema.",
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when the report was generated.",
    )
    title: str = Field(..., description="Report title shown in the UI.")
    summary: str = Field(..., description="Short overall summary for the report.")
    sections: list[ReportSectionBlock] = Field(
        default_factory=list,
        description="The report's three top-level section blocks.",
    )
    evidence_index: list[EvidenceAnchor] = Field(
        default_factory=list,
        description="Deduplicated evidence anchors used across the report.",
    )
    disclaimer: str | None = Field(
        default=None,
        description="Optional product-level disclaimer or uncertainty note.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Report-scoped metadata and tracing information.",
    )

    class Config:
        anystr_strip_whitespace = True

    @root_validator
    def populate_evidence_index(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Backfill a deduplicated evidence index from cards when omitted."""

        sections = values.get("sections") or []
        evidence_index = values.get("evidence_index") or []

        section_names = [section.section for section in sections]
        if len(section_names) != len(set(section_names)):
            raise ValueError("report sections must be unique within one report")

        seen_anchor_ids = {anchor.anchor_id for anchor in evidence_index}
        if len(seen_anchor_ids) != len(evidence_index):
            raise ValueError("anchor_id values must be unique within evidence_index")

        if evidence_index:
            return values

        deduped_anchors: list[EvidenceAnchor] = []
        for section in sections:
            for card in section.cards:
                for anchor in card.evidence:
                    if anchor.anchor_id in seen_anchor_ids:
                        continue
                    deduped_anchors.append(anchor)
                    seen_anchor_ids.add(anchor.anchor_id)

        values["evidence_index"] = deduped_anchors
        return values


__all__ = [
    "AnalysisReportIR",
    "EvidenceAnchor",
    "EvidenceSourceType",
    "ReportCard",
    "ReportCardType",
    "ReportPriority",
    "ReportSection",
    "ReportSectionBlock",
    "TypeCandidate",
]
