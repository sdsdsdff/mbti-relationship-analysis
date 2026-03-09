"""Heuristic behavior signal extraction for MVP chat analysis.

The extractor in this module intentionally stays simple and auditable. It does
not attempt to infer stable personality from sparse evidence. Instead, it turns
observable chat patterns into typed signals that the report layer can reference
with message-level traceability.
"""

from __future__ import annotations

from statistics import median

from src.analyzers.signal_schema import (
    BehaviorSignal,
    BehaviorSignalSet,
    BehaviorSignalType,
    InteractionWindow,
    SignalConfidence,
    SignalStrength,
    SignalSubject,
    SignalValence,
)
from src.parsers.schema import (
    Conversation,
    ConversationParticipant,
    Message,
    MessageRole,
)


_QUESTION_MARKERS = (
    "?",
    "？",
    "吗",
    "呢",
    "为什么",
    "怎么",
    "要不要",
    "想不想",
    "would you",
    "do you",
    "how",
    "what",
    "when",
    "why",
)
_WARMTH_MARKERS = (
    "辛苦",
    "抱抱",
    "想你",
    "开心",
    "可爱",
    "晚安",
    "早点休息",
    "谢谢",
    "喜欢",
    "爱你",
    "哈哈",
    "嘿嘿",
    "😊",
    "😄",
    "🥰",
    "❤️",
    "miss you",
    "good night",
    "thank you",
    "glad",
    "happy",
    "love",
    "hug",
)
_PLANNING_MARKERS = (
    "明天",
    "后天",
    "周末",
    "周六",
    "周日",
    "下次",
    "一起",
    "见面",
    "几点",
    "安排",
    "计划",
    "订位",
    "电影",
    "吃饭",
    "喝咖啡",
    "tomorrow",
    "weekend",
    "next time",
    "plan",
    "schedule",
    "meet",
    "dinner",
    "lunch",
    "coffee",
    "book",
)


class HeuristicSignalExtractor:
    """Extract a small set of evidence-backed chat behavior signals."""

    extractor_name = "heuristic_signal_extractor"
    extractor_version = "0.1.0"

    def extract(self, conversation: Conversation) -> BehaviorSignalSet:
        """Extract MVP behavior signals from one normalized conversation."""

        signals: list[BehaviorSignal] = []
        participants = [
            participant
            for participant in conversation.participants
            if participant.role != MessageRole.SYSTEM
        ]

        for participant in participants:
            participant_messages = [
                message
                for message in conversation.messages
                if message.speaker_id == participant.participant_id
            ]
            if not participant_messages:
                continue

            subject = self._subject_for_participant(participant)
            signals.extend(
                [
                    self._build_initiative_signal(
                        conversation=conversation,
                        participant=participant,
                        participant_messages=participant_messages,
                        subject=subject,
                    ),
                    self._build_responsiveness_signal(
                        conversation=conversation,
                        participant=participant,
                        participant_messages=participant_messages,
                        subject=subject,
                    ),
                    self._build_curiosity_signal(
                        participant=participant,
                        participant_messages=participant_messages,
                        subject=subject,
                    ),
                    self._build_emotional_warmth_signal(
                        participant=participant,
                        participant_messages=participant_messages,
                        subject=subject,
                    ),
                    self._build_planning_signal(
                        participant=participant,
                        participant_messages=participant_messages,
                        subject=subject,
                    ),
                ]
            )

        return BehaviorSignalSet(
            signal_set_id=f"{conversation.conversation_id}_signals",
            conversation_id=conversation.conversation_id,
            extractor_name=self.extractor_name,
            extractor_version=self.extractor_version,
            signals=signals,
            metadata={"message_count": conversation.message_count},
        )

    def _build_initiative_signal(
        self,
        *,
        conversation: Conversation,
        participant: ConversationParticipant,
        participant_messages: list[Message],
        subject: SignalSubject,
    ) -> BehaviorSignal:
        """Measure how often the participant starts or re-starts turns."""

        all_turn_starts = [
            message
            for index, message in enumerate(conversation.messages)
            if message.speaker_id is not None
            and (index == 0 or conversation.messages[index - 1].speaker_id != message.speaker_id)
        ]
        participant_turn_starts = [
            message
            for message in all_turn_starts
            if message.speaker_id == participant.participant_id
        ]

        score = self._clamp(
            len(participant_turn_starts) / max(1, len(all_turn_starts)),
            minimum=0.05,
            maximum=0.95,
        )
        evidence_messages = participant_turn_starts or participant_messages[:2]
        if score >= 0.6:
            summary = "从现有聊天证据看，这一方更常主动开启或推进话题。"
            valence = SignalValence.POSITIVE
        elif score <= 0.35:
            summary = "从现有聊天证据看，这一方更常跟随回应，主动开场相对较少。"
            valence = SignalValence.NEGATIVE
        else:
            summary = "从现有聊天证据看，这一方的主动推进频率与对方接近。"
            valence = SignalValence.MIXED

        return self._build_signal(
            signal_type=BehaviorSignalType.INITIATIVE,
            participant=participant,
            subject=subject,
            summary=summary,
            score=score,
            valence=valence,
            evidence_messages=evidence_messages,
            confidence_score=self._confidence_score(
                evidence_count=len(participant_turn_starts),
                sample_size=len(all_turn_starts),
            ),
            metadata={
                "turn_starts": len(participant_turn_starts),
                "total_turn_starts": len(all_turn_starts),
            },
        )

    def _build_responsiveness_signal(
        self,
        *,
        conversation: Conversation,
        participant: ConversationParticipant,
        participant_messages: list[Message],
        subject: SignalSubject,
    ) -> BehaviorSignal:
        """Measure how promptly the participant replies when the other speaks."""

        reply_pairs: list[tuple[Message, Message, float | None]] = []
        for index, message in enumerate(conversation.messages[1:], start=1):
            previous_message = conversation.messages[index - 1]
            if message.speaker_id != participant.participant_id:
                continue
            if previous_message.speaker_id in {None, participant.participant_id}:
                continue

            delay_minutes: float | None = None
            if previous_message.sent_at is not None and message.sent_at is not None:
                delay_minutes = max(
                    (message.sent_at - previous_message.sent_at).total_seconds() / 60.0,
                    0.0,
                )
            reply_pairs.append((previous_message, message, delay_minutes))

        evidence_messages = [pair[1] for pair in reply_pairs] or participant_messages[:2]
        timed_pairs = [pair for pair in reply_pairs if pair[2] is not None]
        notes: list[str] = []

        if timed_pairs:
            delay_values = [pair[2] for pair in timed_pairs if pair[2] is not None]
            prompt_pairs = [pair for pair in timed_pairs if pair[2] is not None and pair[2] <= 180.0]
            slow_pairs = [pair for pair in timed_pairs if pair[2] is not None and pair[2] >= 1440.0]
            prompt_ratio = len(prompt_pairs) / max(1, len(timed_pairs))
            median_delay = median(delay_values)
            score = self._clamp(
                0.25
                + (prompt_ratio * 0.5)
                + (0.15 if median_delay <= 60.0 else 0.05 if median_delay <= 360.0 else -0.05)
                - (len(slow_pairs) / max(1, len(timed_pairs)) * 0.2),
                minimum=0.05,
                maximum=0.95,
            )
            if score >= 0.6:
                summary = "从回复时间和轮次衔接看，这一方通常会较快接住对话。"
                valence = SignalValence.POSITIVE
                evidence_messages = [pair[1] for pair in prompt_pairs] or evidence_messages
            elif score <= 0.35:
                summary = "从回复时间和轮次衔接看，这一方的回应节奏偏慢或偏弱。"
                valence = SignalValence.NEGATIVE
                evidence_messages = [pair[1] for pair in slow_pairs] or evidence_messages
            else:
                summary = "从回复时间和轮次衔接看，这一方的回应节奏有一定波动。"
                valence = SignalValence.MIXED
        else:
            score = self._clamp(
                0.35 + (len(reply_pairs) / max(1, len(participant_messages)) * 0.35),
                minimum=0.1,
                maximum=0.75,
            )
            summary = "时间戳不足时，先按回合衔接粗略判断这一方有一定回应意愿。"
            valence = SignalValence.NEUTRAL
            notes.append("timestamps unavailable; responsiveness uses turn order only")

        return self._build_signal(
            signal_type=BehaviorSignalType.RESPONSIVENESS,
            participant=participant,
            subject=subject,
            summary=summary,
            score=score,
            valence=valence,
            evidence_messages=evidence_messages,
            confidence_score=self._confidence_score(
                evidence_count=len(reply_pairs),
                sample_size=len(participant_messages),
                timestamp_bonus=bool(timed_pairs),
            ),
            notes=notes,
            counter_messages=[pair[0] for pair in reply_pairs if pair[2] is not None and pair[2] >= 1440.0],
            metadata={
                "reply_count": len(reply_pairs),
                "timed_reply_count": len(timed_pairs),
            },
        )

    def _build_curiosity_signal(
        self,
        *,
        participant: ConversationParticipant,
        participant_messages: list[Message],
        subject: SignalSubject,
    ) -> BehaviorSignal:
        """Measure how often the participant explicitly asks questions."""

        question_messages = [
            message
            for message in participant_messages
            if self._contains_any_marker(message.normalized_text, _QUESTION_MARKERS)
        ]
        ratio = len(question_messages) / max(1, len(participant_messages))
        score = self._clamp(0.1 + (ratio * 0.9), minimum=0.05, maximum=0.95)
        evidence_messages = question_messages or participant_messages[:2]

        if score >= 0.45:
            summary = "从问题和追问的密度看，这一方对对话内容表现出较明显的好奇与了解意愿。"
            valence = SignalValence.POSITIVE
        elif score <= 0.2:
            summary = "从现有聊天证据看，这一方较少主动追问，更多停留在接话层面。"
            valence = SignalValence.NEGATIVE
        else:
            summary = "从现有聊天证据看，这一方会有一些追问，但整体强度中等。"
            valence = SignalValence.MIXED

        return self._build_signal(
            signal_type=BehaviorSignalType.CURIOSITY,
            participant=participant,
            subject=subject,
            summary=summary,
            score=score,
            valence=valence,
            evidence_messages=evidence_messages,
            confidence_score=self._confidence_score(
                evidence_count=len(question_messages),
                sample_size=len(participant_messages),
            ),
            metadata={
                "question_count": len(question_messages),
                "message_count": len(participant_messages),
            },
        )

    def _build_emotional_warmth_signal(
        self,
        *,
        participant: ConversationParticipant,
        participant_messages: list[Message],
        subject: SignalSubject,
    ) -> BehaviorSignal:
        """Measure whether the participant shows warmth or caring language."""

        warm_messages = [
            message
            for message in participant_messages
            if self._contains_any_marker(message.normalized_text, _WARMTH_MARKERS)
        ]
        ratio = len(warm_messages) / max(1, len(participant_messages))
        score = self._clamp(0.12 + (ratio * 0.88), minimum=0.05, maximum=0.95)
        evidence_messages = warm_messages or participant_messages[:2]

        if score >= 0.45:
            summary = "从措辞和情绪表达看，这一方在聊天里释放出较明显的温度与关心。"
            valence = SignalValence.POSITIVE
        elif score <= 0.2:
            summary = "从现有聊天证据看，这一方的情绪温度表达偏克制，外显关心较少。"
            valence = SignalValence.NEGATIVE
        else:
            summary = "从现有聊天证据看，这一方会表达一些善意和关心，但整体偏保守。"
            valence = SignalValence.MIXED

        return self._build_signal(
            signal_type=BehaviorSignalType.EMOTIONAL_WARMTH,
            participant=participant,
            subject=subject,
            summary=summary,
            score=score,
            valence=valence,
            evidence_messages=evidence_messages,
            confidence_score=self._confidence_score(
                evidence_count=len(warm_messages),
                sample_size=len(participant_messages),
            ),
            metadata={
                "warm_message_count": len(warm_messages),
                "message_count": len(participant_messages),
            },
        )

    def _build_planning_signal(
        self,
        *,
        participant: ConversationParticipant,
        participant_messages: list[Message],
        subject: SignalSubject,
    ) -> BehaviorSignal:
        """Measure whether the participant brings up future-oriented coordination."""

        planning_messages = [
            message
            for message in participant_messages
            if self._contains_any_marker(message.normalized_text, _PLANNING_MARKERS)
        ]
        ratio = len(planning_messages) / max(1, len(participant_messages))
        score = self._clamp(0.08 + (ratio * 0.92), minimum=0.05, maximum=0.95)
        evidence_messages = planning_messages or participant_messages[:2]

        if score >= 0.4:
            summary = "从现有聊天证据看，这一方会把互动往具体安排或未来行动上推进。"
            valence = SignalValence.POSITIVE
        elif score <= 0.18:
            summary = "从现有聊天证据看，这一方较少提出明确安排，更多停留在当下回应。"
            valence = SignalValence.NEGATIVE
        else:
            summary = "从现有聊天证据看，这一方偶尔会提安排，但未来导向还不算稳定。"
            valence = SignalValence.MIXED

        return self._build_signal(
            signal_type=BehaviorSignalType.PLANNING_ORIENTATION,
            participant=participant,
            subject=subject,
            summary=summary,
            score=score,
            valence=valence,
            evidence_messages=evidence_messages,
            confidence_score=self._confidence_score(
                evidence_count=len(planning_messages),
                sample_size=len(participant_messages),
            ),
            metadata={
                "planning_message_count": len(planning_messages),
                "message_count": len(participant_messages),
            },
        )

    def _build_signal(
        self,
        *,
        signal_type: BehaviorSignalType,
        participant: ConversationParticipant,
        subject: SignalSubject,
        summary: str,
        score: float,
        valence: SignalValence,
        evidence_messages: list[Message],
        confidence_score: float,
        metadata: dict[str, object] | None = None,
        notes: list[str] | None = None,
        counter_messages: list[Message] | None = None,
    ) -> BehaviorSignal:
        """Build one schema-compliant behavior signal from heuristic outputs."""

        selected_messages = evidence_messages[:3]
        counter_messages = counter_messages or []

        return BehaviorSignal(
            signal_id=f"{signal_type.value}_{participant.participant_id}",
            type=signal_type,
            subject=subject,
            participant_id=participant.participant_id,
            summary=summary,
            strength=SignalStrength(score=score),
            confidence=SignalConfidence(score=confidence_score),
            valence=valence,
            message_ids=[message.message_id for message in selected_messages],
            counter_message_ids=[message.message_id for message in counter_messages[:3]],
            window=self._build_window(selected_messages),
            notes=notes or [],
            metadata=metadata or {},
        )

    def _build_window(self, messages: list[Message]) -> InteractionWindow | None:
        """Convert evidence messages into a lightweight interaction window."""

        if not messages:
            return None

        return InteractionWindow(
            start_message_id=messages[0].message_id,
            end_message_id=messages[-1].message_id,
            start_time=messages[0].sent_at,
            end_time=messages[-1].sent_at,
        )

    def _subject_for_participant(self, participant: ConversationParticipant) -> SignalSubject:
        """Map parser-level participant roles into report-level signal subjects."""

        if participant.role == MessageRole.SELF:
            return SignalSubject.SELF
        return SignalSubject.OTHER

    def _confidence_score(
        self,
        *,
        evidence_count: int,
        sample_size: int,
        timestamp_bonus: bool = False,
    ) -> float:
        """Compute a conservative confidence score from sample size and evidence."""

        score = 0.35 + min(evidence_count, 4) * 0.08 + min(sample_size, 10) * 0.02
        if timestamp_bonus:
            score += 0.08
        return self._clamp(score, minimum=0.25, maximum=0.92)

    def _contains_any_marker(self, text: str | None, markers: tuple[str, ...]) -> bool:
        """Return whether the text contains any of the configured marker phrases."""

        if text is None:
            return False

        normalized = text.casefold()
        return any(marker.casefold() in normalized for marker in markers)

    def _clamp(self, value: float, *, minimum: float, maximum: float) -> float:
        """Clamp one numeric score into the expected 0-1 range."""

        return max(minimum, min(maximum, value))


__all__ = ["HeuristicSignalExtractor"]
