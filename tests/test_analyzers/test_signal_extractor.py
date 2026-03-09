"""Tests for the heuristic behavior signal extractor."""

from src.analyzers.signal_extractor import HeuristicSignalExtractor
from src.analyzers.signal_schema import BehaviorSignalType, SignalSubject, SignalValence
from src.parsers.markdown_parser import MarkdownParser
from src.parsers.normalizer import ConversationNormalizer
from src.parsers.schema import Conversation


def test_signal_extractor_outputs_required_signal_types() -> None:
    """It emits the MVP signal set for a normalized conversation."""

    conversation = _build_normalized_conversation()
    signal_set = HeuristicSignalExtractor().extract(conversation)

    required_types = {
        BehaviorSignalType.INITIATIVE,
        BehaviorSignalType.RESPONSIVENESS,
        BehaviorSignalType.CURIOSITY,
        BehaviorSignalType.EMOTIONAL_WARMTH,
        BehaviorSignalType.PLANNING_ORIENTATION,
    }

    assert signal_set.conversation_id == conversation.conversation_id
    assert signal_set.extractor_name == "heuristic_signal_extractor"
    assert required_types.issubset({signal.type for signal in signal_set.signals})


def test_signal_extractor_binds_key_judgments_to_message_ids() -> None:
    """It keeps message anchors on curiosity and planning signals."""

    conversation = _build_normalized_conversation()
    signal_set = HeuristicSignalExtractor().extract(conversation)
    self_curiosity = next(
        signal
        for signal in signal_set.signals
        if signal.subject == SignalSubject.SELF and signal.type == BehaviorSignalType.CURIOSITY
    )
    self_planning = next(
        signal
        for signal in signal_set.signals
        if signal.subject == SignalSubject.SELF
        and signal.type == BehaviorSignalType.PLANNING_ORIENTATION
    )
    other_responsiveness = next(
        signal
        for signal in signal_set.signals
        if signal.subject == SignalSubject.OTHER
        and signal.type == BehaviorSignalType.RESPONSIVENESS
    )

    assert self_curiosity.message_ids == ["msg_0", "msg_3"]
    assert self_curiosity.valence == SignalValence.POSITIVE
    assert self_planning.message_ids == ["msg_3"]
    assert other_responsiveness.message_ids
    assert other_responsiveness.window is not None


def _build_normalized_conversation() -> Conversation:
    """Create a small timestamped transcript for extractor tests."""

    parser = MarkdownParser(self_names=["Me"])
    conversation = parser.parse_text(
        "# Evening Chat\n"
        "- [2024-03-01 20:00] Me: 到家了吗？\n"
        "- [2024-03-01 20:02] Alex: 到啦，你呢？\n"
        "- [2024-03-01 20:03] Me: 我也到了，今天辛苦啦 😊\n"
        "- [2024-03-01 20:05] Me: 周六要不要一起吃饭？\n"
        "- [2024-03-01 20:08] Alex: 好呀，我来订位\n",
        source_ref="evening_chat.md",
    )
    return ConversationNormalizer().normalize(
        conversation,
        default_language="zh-CN",
        default_timezone="Asia/Shanghai",
    )
