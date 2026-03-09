"""Minimal end-to-end analysis pipeline for local MVP runs."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.analyzers.report_generator import ReportGenerator
from src.analyzers.report_schema import AnalysisReportIR, ReportCard, ReportSectionBlock
from src.analyzers.signal_extractor import HeuristicSignalExtractor
from src.analyzers.signal_schema import BehaviorSignalSet
from src.models.byok_client import BYOKClient, BYOKClientError, LLMClientProtocol
from src.models.llm_result import LLMAnalysisAdapter, LLMReportEnrichment
from src.models.prompt_packager import LLMPromptPackager
from src.parsers.normalizer import ConversationNormalizer
from src.parsers.parser_factory import ParserFactory
from src.parsers.schema import Conversation
from src.utils.config import AppConfig, load_config


@dataclass(frozen=True)
class AnalysisArtifacts:
    """Structured outputs produced by one local analysis run."""

    config: AppConfig
    conversation: Conversation
    signal_set: BehaviorSignalSet
    report: AnalysisReportIR

    def to_dict(self) -> dict[str, object]:
        """Serialize the full pipeline output into plain JSON-compatible data."""

        return {
            "config": json.loads(self.config.json()),
            "conversation": json.loads(self.conversation.json()),
            "signal_set": json.loads(self.signal_set.json()),
            "report": json.loads(self.report.json()),
        }

    def to_json(self, *, indent: int = 2) -> str:
        """Serialize the full pipeline output into a JSON string."""

        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def report_json(self, *, indent: int = 2) -> str:
        """Serialize only the generated report into a JSON string."""

        return self.report.json(indent=indent, ensure_ascii=False)


def analyze_file(
    path: str | Path,
    *,
    self_names: Iterable[str] | None = None,
    config_path: str | Path | None = None,
    background_info: Mapping[str, Any] | None = None,
    llm_client: LLMClientProtocol | None = None,
) -> AnalysisArtifacts:
    """Run the MVP analysis flow for one chat transcript file."""

    config = load_config(config_path=config_path)
    parsed_conversation = ParserFactory.parse_file(path, self_names=self_names)
    normalized_conversation = ConversationNormalizer().normalize(
        parsed_conversation,
        default_timezone=config.default_timezone,
        default_language=config.default_locale,
    )
    signal_set = HeuristicSignalExtractor().extract(normalized_conversation)
    report = ReportGenerator().build(signal_set, conversation=normalized_conversation)
    report = _apply_optional_llm_enrichment(
        report,
        config=config,
        conversation=normalized_conversation,
        signal_set=signal_set,
        background_info=background_info,
        llm_client=llm_client,
    )

    return AnalysisArtifacts(
        config=config,
        conversation=normalized_conversation,
        signal_set=signal_set,
        report=report,
    )


def write_analysis_json(
    artifacts: AnalysisArtifacts,
    output_path: str | Path,
    *,
    report_only: bool = False,
) -> Path:
    """Write the analysis result bundle or report JSON to disk."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = artifacts.report_json() if report_only else artifacts.to_json()
    path.write_text(payload, encoding="utf-8")
    return path


def _apply_optional_llm_enrichment(
    report: AnalysisReportIR,
    *,
    config: AppConfig,
    conversation: Conversation,
    signal_set: BehaviorSignalSet,
    background_info: Mapping[str, Any] | None,
    llm_client: LLMClientProtocol | None,
) -> AnalysisReportIR:
    """Optionally enrich the heuristic report with one BYOK LLM pass."""

    llm_metadata = {
        "enabled": config.byok.enabled,
        "provider": config.byok.provider.value,
        "model": config.byok.model,
        "attempted": False,
        "used": False,
        "fallback_reason": None,
    }
    byok_config = config.byok.resolve_api_key()

    if not byok_config.enabled:
        llm_metadata["fallback_reason"] = "disabled"
        return _update_report_metadata(report, llm_metadata)

    if not byok_config.api_key:
        llm_metadata["fallback_reason"] = "missing_api_key"
        return _update_report_metadata(report, llm_metadata)

    prompt_bundle = LLMPromptPackager().build(
        conversation,
        signal_set,
        background_info=background_info,
    )
    llm_metadata.update(
        {
            "attempted": True,
            "prompt_message_count": len(prompt_bundle.messages),
            "prompt_signal_count": prompt_bundle.metadata.get("signal_count", 0),
        }
    )

    client = llm_client or BYOKClient(byok_config)
    try:
        raw_result = client.analyze(prompt_bundle)
        enrichment = LLMAnalysisAdapter().adapt(raw_result)
    except (BYOKClientError, TypeError, ValueError) as exc:
        llm_metadata.update(
            {
                "used": False,
                "fallback_reason": "client_error",
                "error_type": exc.__class__.__name__,
                "error_message": str(exc),
            }
        )
        return _update_report_metadata(report, llm_metadata)

    llm_metadata.update(
        {
            "used": True,
            "fallback_reason": None,
            "card_count": len(enrichment.cards),
        }
    )
    enriched_report = _merge_llm_enrichment(report, enrichment)
    return _update_report_metadata(enriched_report, llm_metadata)


def _merge_llm_enrichment(
    report: AnalysisReportIR,
    enrichment: LLMReportEnrichment,
) -> AnalysisReportIR:
    """Append LLM-produced cards to the existing heuristic report sections."""

    cards_by_section: dict[str, list[ReportCard]] = {}
    for card in enrichment.cards:
        cards_by_section.setdefault(card.section.value, []).append(card)

    updated_sections: list[ReportSectionBlock] = []
    for section in report.sections:
        additional_cards = cards_by_section.get(section.section.value, [])
        updated_sections.append(
            section.copy(update={"cards": [*section.cards, *additional_cards]}, deep=True)
        )

    return _rebuild_report(report, sections=updated_sections)


def _update_report_metadata(
    report: AnalysisReportIR,
    llm_metadata: dict[str, Any],
) -> AnalysisReportIR:
    """Return a validated report copy with LLM enrichment status metadata."""

    metadata = dict(report.metadata)
    metadata["llm_enrichment"] = llm_metadata
    return _rebuild_report(report, metadata=metadata)


def _rebuild_report(
    report: AnalysisReportIR,
    *,
    sections: list[ReportSectionBlock] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AnalysisReportIR:
    """Reconstruct the validated report after section or metadata updates."""

    payload = report.dict(exclude={"evidence_index"})
    if sections is not None:
        payload["sections"] = sections
    if metadata is not None:
        payload["metadata"] = metadata
    return AnalysisReportIR(**payload)


__all__ = ["AnalysisArtifacts", "analyze_file", "write_analysis_json"]
