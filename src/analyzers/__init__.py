"""Analysis-layer schemas and helpers."""

from .report_schema import (
    AnalysisReportIR,
    EvidenceAnchor,
    EvidenceSourceType,
    ReportCard,
    ReportCardType,
    ReportPriority,
    ReportSection,
    ReportSectionBlock,
    TypeCandidate,
)
from .report_generator import ReportGenerator
from .signal_extractor import HeuristicSignalExtractor
from .signal_schema import (
    BehaviorSignal,
    BehaviorSignalCategory,
    BehaviorSignalSet,
    BehaviorSignalType,
    ConfidenceBand,
    InteractionWindow,
    SignalConfidence,
    SignalEvidenceSource,
    SignalStrength,
    SignalStrengthBand,
    SignalSubject,
    SignalValence,
)

__all__ = [
    "AnalysisReportIR",
    "BehaviorSignal",
    "BehaviorSignalCategory",
    "BehaviorSignalSet",
    "BehaviorSignalType",
    "ConfidenceBand",
    "EvidenceAnchor",
    "EvidenceSourceType",
    "HeuristicSignalExtractor",
    "InteractionWindow",
    "ReportGenerator",
    "ReportCard",
    "ReportCardType",
    "ReportPriority",
    "ReportSection",
    "ReportSectionBlock",
    "SignalConfidence",
    "SignalEvidenceSource",
    "SignalStrength",
    "SignalStrengthBand",
    "SignalSubject",
    "SignalValence",
    "TypeCandidate",
]
