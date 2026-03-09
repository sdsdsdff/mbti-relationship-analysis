"""Minimal end-to-end analysis pipeline for local MVP runs."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

from src.analyzers.report_generator import ReportGenerator
from src.analyzers.report_schema import AnalysisReportIR
from src.analyzers.signal_extractor import HeuristicSignalExtractor
from src.analyzers.signal_schema import BehaviorSignalSet
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


__all__ = ["AnalysisArtifacts", "analyze_file", "write_analysis_json"]
