"""Minimal schema and adapters for BYOK model analysis results.

The MVP adapter intentionally keeps the surface area small. It validates the
model's JSON response, converts it into typed intermediate objects, and then
maps those objects into `AnalysisReportIR`-compatible cards that can be merged
into the existing heuristic report.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Mapping

from src.compat.pydantic import BaseModel, Field, validator

from src.analyzers.report_schema import (
    EvidenceAnchor,
    EvidenceSourceType,
    ReportCard,
    ReportCardType,
    ReportPriority,
    ReportSection,
    TypeCandidate,
)


class LLMTypeAssessmentSubject(str, Enum):
    """Subjects that can receive tentative type assessments in the MVP flow."""

    SELF = "self"
    OTHER = "other"


class LLMTypeAssessment(BaseModel):
    """Tentative MBTI candidate set for one participant."""

    subject: LLMTypeAssessmentSubject = Field(
        ...,
        description="Which participant the tentative type assessment refers to.",
    )
    summary: str = Field(..., description="Conservative explanation for the candidate set.")
    candidates: list[TypeCandidate] = Field(
        default_factory=list,
        description="Tentative MBTI candidates ordered by relative fit.",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Overall confidence for the tentative type assessment.",
    )
    signal_ids: list[str] = Field(
        default_factory=list,
        description="Supporting heuristic signal identifiers referenced by the model.",
    )

    class Config:
        anystr_strip_whitespace = True

    @validator("candidates")
    def require_candidates(cls, value: list[TypeCandidate]) -> list[TypeCandidate]:
        """Ensure each tentative type assessment includes at least one candidate."""

        if not value:
            raise ValueError("type assessments must include at least one candidate")
        return value


class LLMAnalysisInsight(BaseModel):
    """One LLM-authored insight that can be rendered as a report card."""

    section: ReportSection = Field(..., description="Report section receiving the insight.")
    title: str = Field(..., description="Short display title for the insight card.")
    summary: str = Field(..., description="Main summary text for the insight card.")
    bullets: list[str] = Field(
        default_factory=list,
        description="Optional supporting bullets for the insight card.",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence assigned by the model for this insight.",
    )
    signal_ids: list[str] = Field(
        default_factory=list,
        description="Supporting heuristic signal identifiers referenced by the model.",
    )

    class Config:
        anystr_strip_whitespace = True


class LLMAnalysisResult(BaseModel):
    """Typed representation of one model-returned JSON payload."""

    summary: str | None = Field(
        default=None,
        description="Optional short global summary for the enrichment result.",
    )
    type_assessments: list[LLMTypeAssessment] = Field(
        default_factory=list,
        description="Tentative type assessments for self and/or other.",
    )
    insights: list[LLMAnalysisInsight] = Field(
        default_factory=list,
        description="Additional report-ready insights produced by the model.",
    )
    uncertainty_notes: list[str] = Field(
        default_factory=list,
        description="Explicit caveats carried into the final report.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional raw-model metadata preserved for tracing.",
    )

    class Config:
        anystr_strip_whitespace = True


class LLMReportEnrichment(BaseModel):
    """Intermediate report enrichment generated from a validated LLM result."""

    summary: str | None = Field(
        default=None,
        description="Optional report-level summary contributed by the model.",
    )
    cards: list[ReportCard] = Field(
        default_factory=list,
        description="Report cards ready to merge into the heuristic report.",
    )
    uncertainty_notes: list[str] = Field(
        default_factory=list,
        description="Explicit uncertainty notes preserved alongside the cards.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Trace metadata about the enrichment output.",
    )

    class Config:
        anystr_strip_whitespace = True


class LLMAnalysisAdapter:
    """Validate raw LLM JSON and adapt it into report-friendly enrichment data."""

    def parse(self, payload: str | Mapping[str, Any] | LLMAnalysisResult) -> LLMAnalysisResult:
        """Normalize a raw JSON string or mapping into `LLMAnalysisResult`."""

        if isinstance(payload, LLMAnalysisResult):
            return payload
        if isinstance(payload, str):
            parsed_payload = json.loads(payload)
        elif isinstance(payload, Mapping):
            parsed_payload = dict(payload)
        else:
            raise TypeError("payload must be a JSON string, mapping, or LLMAnalysisResult")
        return LLMAnalysisResult(**parsed_payload)

    def adapt(self, payload: str | Mapping[str, Any] | LLMAnalysisResult) -> LLMReportEnrichment:
        """Convert a raw payload directly into report-ready enrichment output."""

        return self.to_report_enrichment(self.parse(payload))

    def to_report_enrichment(self, result: LLMAnalysisResult) -> LLMReportEnrichment:
        """Build report cards from the validated LLM result."""

        cards: list[ReportCard] = []

        if result.summary:
            cards.append(
                ReportCard(
                    card_id="llm_overview_card",
                    section=ReportSection.OVERVIEW,
                    type=ReportCardType.CURRENT_STAGE,
                    title="LLM 补充观察",
                    summary=result.summary,
                    bullets=[],
                    priority=ReportPriority.SECONDARY,
                    tags=["llm", "byok", "conservative"],
                    payload={"source": "llm_enrichment"},
                )
            )

        for index, assessment in enumerate(result.type_assessments):
            cards.append(self._build_type_card(assessment=assessment, index=index))

        for index, insight in enumerate(result.insights):
            cards.append(self._build_insight_card(insight=insight, index=index))

        if result.uncertainty_notes:
            cards.append(self._build_uncertainty_card(result.uncertainty_notes))

        return LLMReportEnrichment(
            summary=result.summary,
            cards=cards,
            uncertainty_notes=list(result.uncertainty_notes),
            metadata={
                "card_count": len(cards),
                "type_assessment_count": len(result.type_assessments),
                "insight_count": len(result.insights),
                "uncertainty_count": len(result.uncertainty_notes),
                **dict(result.metadata),
            },
        )

    def _build_type_card(self, *, assessment: LLMTypeAssessment, index: int) -> ReportCard:
        """Convert one tentative type assessment into a report card."""

        section = ReportSection(assessment.subject.value)
        title = (
            "你的可能类型（LLM 辅助）"
            if assessment.subject == LLMTypeAssessmentSubject.SELF
            else "对方的可能类型（LLM 辅助）"
        )
        evidence = [
            EvidenceAnchor(
                anchor_id=f"llm_type_{assessment.subject.value}_{index}_anchor",
                source_type=EvidenceSourceType.DERIVED_SIGNAL,
                source_ref=f"llm_type_{assessment.subject.value}_{index}",
                summary="Tentative LLM-supported type hypothesis grounded in supplied signals.",
                signal_ids=list(assessment.signal_ids),
                confidence=assessment.confidence,
            )
        ]
        return ReportCard(
            card_id=f"llm_type_{assessment.subject.value}_{index}",
            section=section,
            type=(
                ReportCardType.LIKELY_TYPE
                if len(assessment.candidates) == 1
                else ReportCardType.TYPE_CANDIDATES
            ),
            title=title,
            summary=assessment.summary,
            bullets=[
                "以下候选只表示当前样本下的暂定倾向，不是固定人格定论。"
            ],
            confidence=assessment.confidence,
            priority=ReportPriority.SECONDARY,
            candidates=list(assessment.candidates),
            signal_ids=list(assessment.signal_ids),
            evidence=evidence,
            tags=["llm", "byok", "tentative", assessment.subject.value],
            payload={"source": "llm_enrichment"},
        )

    def _build_insight_card(self, *, insight: LLMAnalysisInsight, index: int) -> ReportCard:
        """Convert one LLM insight into a report card with conservative defaults."""

        evidence = [
            EvidenceAnchor(
                anchor_id=f"llm_{insight.section.value}_{index}_anchor",
                source_type=EvidenceSourceType.DERIVED_SIGNAL,
                source_ref=f"llm_{insight.section.value}_{index}",
                summary="LLM-added insight linked back to the supplied heuristic signals.",
                signal_ids=list(insight.signal_ids),
                confidence=insight.confidence,
            )
        ]
        return ReportCard(
            card_id=f"llm_{insight.section.value}_{index}",
            section=insight.section,
            type=self._card_type_for_section(insight.section),
            title=insight.title,
            summary=insight.summary,
            bullets=list(insight.bullets),
            confidence=insight.confidence,
            priority=ReportPriority.SECONDARY,
            signal_ids=list(insight.signal_ids),
            evidence=evidence,
            tags=["llm", "byok", insight.section.value],
            payload={"source": "llm_enrichment"},
        )

    def _build_uncertainty_card(self, uncertainty_notes: list[str]) -> ReportCard:
        """Convert uncertainty notes into one overview card."""

        return ReportCard(
            card_id="llm_uncertainty_card",
            section=ReportSection.OVERVIEW,
            type=ReportCardType.UNCERTAINTY,
            title="LLM 不确定性提示",
            summary="以下因素会限制这次 LLM 辅助分析的稳定性，请与启发式信号一起阅读。",
            bullets=list(uncertainty_notes),
            priority=ReportPriority.SECONDARY,
            tags=["llm", "byok", "uncertainty"],
            payload={"source": "llm_enrichment"},
        )

    def _card_type_for_section(self, section: ReportSection) -> ReportCardType:
        """Map one section to the most suitable existing report card type."""

        mapping = {
            ReportSection.OVERVIEW: ReportCardType.CURRENT_STAGE,
            ReportSection.SELF: ReportCardType.CURRENT_STAGE,
            ReportSection.OTHER: ReportCardType.CURRENT_STAGE,
            ReportSection.RELATIONSHIP: ReportCardType.RELATIONSHIP_DYNAMIC,
            ReportSection.ADVICE: ReportCardType.COMMUNICATION_ADVICE,
        }
        return mapping[section]


__all__ = [
    "LLMAnalysisAdapter",
    "LLMAnalysisInsight",
    "LLMAnalysisResult",
    "LLMReportEnrichment",
    "LLMTypeAssessment",
    "LLMTypeAssessmentSubject",
]
