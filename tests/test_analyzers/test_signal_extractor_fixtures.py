"""Fixture-driven tests for the heuristic signal extractor."""

from pathlib import Path

from src.analyzers.signal_extractor import HeuristicSignalExtractor
from src.analyzers.signal_schema import BehaviorSignal, BehaviorSignalType, SignalSubject, SignalValence
from src.parsers.normalizer import ConversationNormalizer
from src.parsers.parser_factory import ParserFactory
from src.parsers.schema import Conversation


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_flirty_fixture_shows_positive_warmth_and_planning() -> None:
    """It detects warmer and more future-oriented signals in the positive sample."""

    conversation = _load_fixture("flirty_positive_chat.md")
    signal_set = HeuristicSignalExtractor().extract(conversation)
    other_warmth = _find_signal(
        signal_set.signals,
        subject=SignalSubject.OTHER,
        signal_type=BehaviorSignalType.EMOTIONAL_WARMTH,
    )
    other_planning = _find_signal(
        signal_set.signals,
        subject=SignalSubject.OTHER,
        signal_type=BehaviorSignalType.PLANNING_ORIENTATION,
    )

    assert other_warmth.valence == SignalValence.POSITIVE
    assert other_warmth.strength.score >= 0.45
    assert other_planning.valence == SignalValence.POSITIVE
    assert other_planning.message_ids == ["msg_5", "msg_7"]


def test_cold_fixture_shows_weaker_responsiveness_and_warmth() -> None:
    """It detects slower and colder interaction patterns in the distant sample."""

    conversation = _load_fixture("distant_cold_chat.txt")
    signal_set = HeuristicSignalExtractor().extract(conversation)
    other_responsiveness = _find_signal(
        signal_set.signals,
        subject=SignalSubject.OTHER,
        signal_type=BehaviorSignalType.RESPONSIVENESS,
    )
    other_warmth = _find_signal(
        signal_set.signals,
        subject=SignalSubject.OTHER,
        signal_type=BehaviorSignalType.EMOTIONAL_WARMTH,
    )

    assert other_responsiveness.valence == SignalValence.NEGATIVE
    assert other_responsiveness.message_ids == ["msg_3", "msg_5"]
    assert other_warmth.valence == SignalValence.NEGATIVE
    assert other_warmth.strength.score <= 0.2


def _load_fixture(filename: str) -> Conversation:
    """Parse and normalize one transcript fixture for analyzer tests."""

    parsed = ParserFactory.parse_file(FIXTURES_DIR / filename, self_names=["Me"])
    return ConversationNormalizer().normalize(
        parsed,
        default_language="zh-CN",
        default_timezone="Asia/Shanghai",
    )


def _find_signal(
    signals: list[BehaviorSignal],
    *,
    subject: SignalSubject,
    signal_type: BehaviorSignalType,
) -> BehaviorSignal:
    """Return the first signal that matches the expected subject and type."""

    return next(
        signal
        for signal in signals
        if signal.subject == subject and signal.type == signal_type
    )
