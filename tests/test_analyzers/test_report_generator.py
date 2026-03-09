"""Tests for the MVP report generator."""

from pathlib import Path

from src.analyzers.report_generator import ReportGenerator
from src.analyzers.report_schema import ReportCardType, ReportSection
from src.analyzers.signal_extractor import HeuristicSignalExtractor
from src.parsers.normalizer import ConversationNormalizer
from src.parsers.parser_factory import ParserFactory
from src.parsers.schema import Conversation


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_report_generator_creates_all_mvp_sections() -> None:
    """It generates the overview/self/other/relationship/advice sections."""

    conversation = _load_conversation()
    signal_set = HeuristicSignalExtractor().extract(conversation)
    report = ReportGenerator().build(signal_set, conversation=conversation)

    assert [section.section for section in report.sections] == [
        ReportSection.OVERVIEW,
        ReportSection.SELF,
        ReportSection.OTHER,
        ReportSection.RELATIONSHIP,
        ReportSection.ADVICE,
    ]
    assert all(section.cards for section in report.sections)
    assert report.disclaimer is not None
    assert "evidence-based" in report.disclaimer


def test_report_generator_attaches_message_backed_evidence() -> None:
    """It keeps report cards traceable back to signal and message evidence."""

    conversation = _load_conversation()
    signal_set = HeuristicSignalExtractor().extract(conversation)
    report = ReportGenerator().build(signal_set, conversation=conversation)
    advice_section = next(
        section for section in report.sections if section.section == ReportSection.ADVICE
    )
    advice_card = advice_section.cards[0]

    assert advice_card.type == ReportCardType.COMMUNICATION_ADVICE
    assert advice_card.bullets
    assert advice_card.evidence
    assert report.evidence_index
    assert report.evidence_index[0].message_ids


def _load_conversation() -> Conversation:
    """Load the positive fixture conversation for report tests."""

    parsed = ParserFactory.parse_file(FIXTURES_DIR / "flirty_positive_chat.md", self_names=["Me"])
    return ConversationNormalizer().normalize(
        parsed,
        default_language="zh-CN",
        default_timezone="Asia/Shanghai",
    )
