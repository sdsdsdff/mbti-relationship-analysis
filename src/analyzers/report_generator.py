"""MVP report generation from extracted behavior signals.

The report generator keeps wording deliberately conservative. It summarizes the
observable interaction patterns supported by the current transcript and avoids
claiming that a short chat sample can fully define personality or relationship
outcomes.
"""

from __future__ import annotations

from src.analyzers.report_schema import (
    AnalysisReportIR,
    EvidenceAnchor,
    EvidenceSourceType,
    ReportCard,
    ReportCardType,
    ReportPriority,
    ReportSection,
    ReportSectionBlock,
)
from src.analyzers.signal_schema import BehaviorSignal, BehaviorSignalSet, SignalSubject
from src.parsers.schema import Conversation, Message


class ReportGenerator:
    """Generate a minimal evidence-based report from behavior signals."""

    generator_name = "mvp_report_generator"
    generator_version = "0.1.0"

    def build(
        self,
        signal_set: BehaviorSignalSet,
        *,
        conversation: Conversation | None = None,
    ) -> AnalysisReportIR:
        """Build the report IR sections needed by the MVP product flow."""

        signals_by_subject = {
            SignalSubject.SELF: [
                signal for signal in signal_set.signals if signal.subject == SignalSubject.SELF
            ],
            SignalSubject.OTHER: [
                signal for signal in signal_set.signals if signal.subject == SignalSubject.OTHER
            ],
        }
        title_source = conversation.title if conversation is not None else signal_set.conversation_id

        overview_card = self._build_overview_card(
            signal_set=signal_set,
            conversation=conversation,
            self_signals=signals_by_subject[SignalSubject.SELF],
            other_signals=signals_by_subject[SignalSubject.OTHER],
        )
        self_card = self._build_subject_card(
            section=ReportSection.SELF,
            title="你的互动侧重点",
            signals=signals_by_subject[SignalSubject.SELF],
            conversation=conversation,
        )
        other_card = self._build_subject_card(
            section=ReportSection.OTHER,
            title="对方的互动侧重点",
            signals=signals_by_subject[SignalSubject.OTHER],
            conversation=conversation,
        )
        relationship_card = self._build_relationship_card(
            self_signals=signals_by_subject[SignalSubject.SELF],
            other_signals=signals_by_subject[SignalSubject.OTHER],
            conversation=conversation,
        )
        advice_card = self._build_advice_card(
            self_signals=signals_by_subject[SignalSubject.SELF],
            other_signals=signals_by_subject[SignalSubject.OTHER],
            conversation=conversation,
        )

        sections = [
            ReportSectionBlock(
                section=ReportSection.OVERVIEW,
                headline="整体概览",
                summary="先看可见互动模式，再进入角色与关系层面的解读。",
                cards=[overview_card],
            ),
            ReportSectionBlock(
                section=ReportSection.SELF,
                headline="我",
                summary="这些观察只描述当前样本里的聊天表现。",
                cards=[self_card],
            ),
            ReportSectionBlock(
                section=ReportSection.OTHER,
                headline="TA",
                summary="这里描述的是对方在这份聊天记录里的互动风格，不是固定人格判定。",
                cards=[other_card],
            ),
            ReportSectionBlock(
                section=ReportSection.RELATIONSHIP,
                headline="我们",
                summary="重点看节奏差、温度差和推进方式是否匹配。",
                cards=[relationship_card],
            ),
            ReportSectionBlock(
                section=ReportSection.ADVICE,
                headline="建议",
                summary="建议只针对当前证据里的沟通模式，适合小步尝试。",
                cards=[advice_card],
            ),
        ]

        return AnalysisReportIR(
            report_id=f"{signal_set.conversation_id}_report",
            conversation_id=signal_set.conversation_id,
            title=f"{title_source} · MVP Relationship Analysis",
            summary=overview_card.summary,
            sections=sections,
            disclaimer=(
                "This MVP report is evidence-based and directional. It summarizes "
                "observable chat patterns rather than making fixed personality or "
                "relationship claims."
            ),
            metadata={
                "generator_name": self.generator_name,
                "generator_version": self.generator_version,
                "signal_count": len(signal_set.signals),
                "extractor_name": signal_set.extractor_name,
            },
        )

    def _build_overview_card(
        self,
        *,
        signal_set: BehaviorSignalSet,
        conversation: Conversation | None,
        self_signals: list[BehaviorSignal],
        other_signals: list[BehaviorSignal],
    ) -> ReportCard:
        """Create the top-level overview card."""

        total_messages = conversation.message_count if conversation is not None else 0
        warmth_balance = self._compare_signal(self_signals, other_signals, "emotional_warmth")
        initiative_balance = self._compare_signal(self_signals, other_signals, "initiative")
        planning_balance = self._compare_signal(
            self_signals,
            other_signals,
            "planning_orientation",
        )
        summary = (
            f"这份 MVP 报告基于 {len(signal_set.signals)} 个可解释信号"
            f"和 {total_messages} 条消息，更适合用来理解当前互动模式，"
            "不适合当作关系定论。"
        )

        anchors = self._anchors_for_signals(
            card_id="overview_card",
            signals=(self_signals + other_signals)[:2],
            conversation=conversation,
        )
        return ReportCard(
            card_id="overview_card",
            section=ReportSection.OVERVIEW,
            type=ReportCardType.CURRENT_STAGE,
            title="当前互动概览",
            summary=summary,
            bullets=[initiative_balance, warmth_balance, planning_balance],
            confidence=self._average_confidence(self_signals + other_signals),
            priority=ReportPriority.PRIMARY,
            signal_ids=[signal.signal_id for signal in (self_signals + other_signals)[:4]],
            evidence=anchors,
            tags=["mvp", "evidence-based"],
        )

    def _build_subject_card(
        self,
        *,
        section: ReportSection,
        title: str,
        signals: list[BehaviorSignal],
        conversation: Conversation | None,
    ) -> ReportCard:
        """Create one section card for self or other."""

        strongest_signal = max(signals, key=lambda signal: signal.strength.score)
        weakest_signal = min(signals, key=lambda signal: signal.strength.score)
        bullets = [
            f"更明显的互动倾向：{self._humanize_signal_type(strongest_signal.type.value)}。",
            f"相对保守的部分：{self._humanize_signal_type(weakest_signal.type.value)}。",
        ]
        summary = (
            f"从当前聊天样本看，{strongest_signal.summary}"
            f"同时，{weakest_signal.summary}"
        )
        card_type = (
            ReportCardType.STRENGTHS
            if strongest_signal.strength.score >= 0.5
            else ReportCardType.BLIND_SPOTS
        )

        return ReportCard(
            card_id=f"{section.value}_card",
            section=section,
            type=card_type,
            title=title,
            summary=summary,
            bullets=bullets,
            confidence=self._average_confidence([strongest_signal, weakest_signal]),
            priority=ReportPriority.PRIMARY,
            signal_ids=[strongest_signal.signal_id, weakest_signal.signal_id],
            evidence=self._anchors_for_signals(
                card_id=f"{section.value}_card",
                signals=[strongest_signal, weakest_signal],
                conversation=conversation,
            ),
            tags=[section.value],
        )

    def _build_relationship_card(
        self,
        *,
        self_signals: list[BehaviorSignal],
        other_signals: list[BehaviorSignal],
        conversation: Conversation | None,
    ) -> ReportCard:
        """Create the relationship dynamics card."""

        self_responsiveness = self._find_signal(self_signals, "responsiveness")
        other_responsiveness = self._find_signal(other_signals, "responsiveness")
        self_warmth = self._find_signal(self_signals, "emotional_warmth")
        other_warmth = self._find_signal(other_signals, "emotional_warmth")

        if (
            self_responsiveness is not None
            and other_responsiveness is not None
            and self_responsiveness.strength.score >= 0.55
            and other_responsiveness.strength.score >= 0.55
            and self_warmth is not None
            and other_warmth is not None
            and self_warmth.strength.score >= 0.45
            and other_warmth.strength.score >= 0.45
        ):
            summary = "当前样本里的互动节奏偏积极，双方都能接住话题，也愿意释放一定情绪温度。"
            bullets = [
                "回复衔接整体顺畅，没有明显单向拖拽。",
                "温度表达和推进意愿都能在聊天里看到。",
            ]
        else:
            summary = "当前样本更像是节奏和温度存在差异的互动，需要靠更明确的沟通来减少误读。"
            bullets = [
                "至少一方的回应节奏偏慢或偏弱。",
                "至少一方较少主动释放关心或具体安排。",
            ]

        supporting_signals = [
            signal
            for signal in [self_responsiveness, other_responsiveness, self_warmth, other_warmth]
            if signal is not None
        ]

        return ReportCard(
            card_id="relationship_card",
            section=ReportSection.RELATIONSHIP,
            type=ReportCardType.RELATIONSHIP_DYNAMIC,
            title="互动动态",
            summary=summary,
            bullets=bullets,
            confidence=self._average_confidence(supporting_signals),
            priority=ReportPriority.PRIMARY,
            signal_ids=[signal.signal_id for signal in supporting_signals],
            evidence=self._anchors_for_signals(
                card_id="relationship_card",
                signals=supporting_signals[:3],
                conversation=conversation,
            ),
            tags=["relationship"],
        )

    def _build_advice_card(
        self,
        *,
        self_signals: list[BehaviorSignal],
        other_signals: list[BehaviorSignal],
        conversation: Conversation | None,
    ) -> ReportCard:
        """Create a cautious communication advice card."""

        advice_bullets: list[str] = []
        supporting_signals: list[BehaviorSignal] = []

        self_planning = self._find_signal(self_signals, "planning_orientation")
        other_planning = self._find_signal(other_signals, "planning_orientation")
        other_responsiveness = self._find_signal(other_signals, "responsiveness")
        other_warmth = self._find_signal(other_signals, "emotional_warmth")

        if other_responsiveness is not None and other_responsiveness.strength.score <= 0.35:
            advice_bullets.append("把期待说具体，例如约定忙完后回一句，而不是留在模糊等待里。")
            supporting_signals.append(other_responsiveness)
        if other_warmth is not None and other_warmth.strength.score <= 0.25:
            advice_bullets.append("少做读心，多给清晰确认；需要关心时尽量直接表达。")
            supporting_signals.append(other_warmth)
        if (
            self_planning is not None
            and other_planning is not None
            and abs(self_planning.strength.score - other_planning.strength.score) >= 0.2
        ):
            advice_bullets.append("把邀约收敛成具体时间和选项，降低双方对推进节奏的理解偏差。")
            supporting_signals.extend([self_planning, other_planning])

        if not advice_bullets:
            advice_bullets = [
                "延续目前有效的回应节奏，同时继续用具体问题和具体安排来减少误解。",
                "把积极反馈说得更明确，会比默认对方能读懂更稳。",
            ]
            supporting_signals = [
                signal for signal in [self_planning, other_planning, other_responsiveness] if signal is not None
            ]

        return ReportCard(
            card_id="advice_card",
            section=ReportSection.ADVICE,
            type=ReportCardType.COMMUNICATION_ADVICE,
            title="下一步建议",
            summary="这些建议只面向当前样本里看得到的沟通模式，适合小范围试用后再观察反馈。",
            bullets=advice_bullets,
            confidence=self._average_confidence(supporting_signals),
            priority=ReportPriority.PRIMARY,
            signal_ids=[signal.signal_id for signal in supporting_signals],
            evidence=self._anchors_for_signals(
                card_id="advice_card",
                signals=supporting_signals[:3],
                conversation=conversation,
            ),
            tags=["advice", "conservative"],
        )

    def _anchors_for_signals(
        self,
        *,
        card_id: str,
        signals: list[BehaviorSignal],
        conversation: Conversation | None,
    ) -> list[EvidenceAnchor]:
        """Build lightweight report anchors from the supporting signals."""

        anchors: list[EvidenceAnchor] = []
        for index, signal in enumerate(signals):
            if conversation is not None and signal.message_ids:
                excerpt = self._excerpt_from_message_ids(conversation, signal.message_ids)
                anchors.append(
                    EvidenceAnchor(
                        anchor_id=f"{card_id}_anchor_{index}",
                        source_type=EvidenceSourceType.CHAT_MESSAGE,
                        message_ids=signal.message_ids,
                        excerpt=excerpt,
                        summary=signal.summary,
                        signal_ids=[signal.signal_id],
                        confidence=signal.confidence.score,
                    )
                )
                continue

            anchors.append(
                EvidenceAnchor(
                    anchor_id=f"{card_id}_anchor_{index}",
                    source_type=EvidenceSourceType.DERIVED_SIGNAL,
                    source_ref=signal.signal_id,
                    summary=signal.summary,
                    signal_ids=[signal.signal_id],
                    confidence=signal.confidence.score,
                )
            )

        return anchors

    def _excerpt_from_message_ids(
        self,
        conversation: Conversation,
        message_ids: list[str],
    ) -> str | None:
        """Create a short UI-friendly excerpt from referenced message ids."""

        message_lookup = {message.message_id: message for message in conversation.messages}
        snippets = [
            self._format_message_snippet(message_lookup[message_id])
            for message_id in message_ids
            if message_id in message_lookup
        ]
        if not snippets:
            return None
        return " / ".join(snippets[:2])

    def _format_message_snippet(self, message: Message) -> str:
        """Format one short message snippet for evidence display."""

        speaker_name = message.speaker_name or "Unknown"
        text = message.normalized_text or message.text or ""
        return f"{speaker_name}: {text}".strip()

    def _find_signal(
        self,
        signals: list[BehaviorSignal],
        signal_type: str,
    ) -> BehaviorSignal | None:
        """Return the first signal with the expected type value."""

        for signal in signals:
            if signal.type.value == signal_type:
                return signal
        return None

    def _compare_signal(
        self,
        self_signals: list[BehaviorSignal],
        other_signals: list[BehaviorSignal],
        signal_type: str,
    ) -> str:
        """Create one plain-language comparison bullet for a signal type."""

        self_signal = self._find_signal(self_signals, signal_type)
        other_signal = self._find_signal(other_signals, signal_type)
        if self_signal is None or other_signal is None:
            return "当前样本不足以比较这一维度。"

        difference = self_signal.strength.score - other_signal.strength.score
        label = self._humanize_signal_type(signal_type)
        if abs(difference) < 0.12:
            return f"{label}：双方在当前样本里相对接近。"
        if difference > 0:
            return f"{label}：你这边表现得更明显一些。"
        return f"{label}：对方这边表现得更明显一些。"

    def _humanize_signal_type(self, signal_type: str) -> str:
        """Map internal signal names to short Chinese UI labels."""

        labels = {
            "initiative": "主动推进",
            "responsiveness": "回应节奏",
            "curiosity": "追问兴趣",
            "emotional_warmth": "情绪温度",
            "planning_orientation": "未来安排",
        }
        return labels.get(signal_type, signal_type.replace("_", " "))

    def _average_confidence(self, signals: list[BehaviorSignal]) -> float | None:
        """Return the average confidence across the provided signals."""

        if not signals:
            return None
        return sum(signal.confidence.score for signal in signals) / len(signals)


__all__ = ["ReportGenerator"]
