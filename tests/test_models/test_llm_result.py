"""Tests for the MVP LLM analysis result adapter layer."""

from __future__ import annotations

from src.analyzers.report_schema import ReportCardType, ReportSection
from src.models.llm_result import LLMAnalysisAdapter, LLMAnalysisResult


def test_llm_analysis_adapter_parses_json_string() -> None:
    """It parses a model JSON string into the typed MVP result schema."""

    result = LLMAnalysisAdapter().parse(
        """
        {
          "summary": "这是一份偏谨慎的补充观察。",
          "type_assessments": [
            {
              "subject": "self",
              "summary": "更像偏外向探索型，但证据仍有限。",
              "confidence": 0.53,
              "signal_ids": ["signal_initiative_self"],
              "candidates": [
                {
                  "mbti_type": "ENFP",
                  "score": 0.42,
                  "why_like": ["主动发起和情绪表达较明显"],
                  "why_not_like": ["样本很短"]
                },
                {
                  "mbti_type": "ENTP",
                  "score": 0.31,
                  "why_like": ["推进和好奇心有迹象"],
                  "why_not_like": ["缺少更长期样本"]
                }
              ]
            }
          ],
          "insights": [
            {
              "section": "relationship",
              "title": "节奏匹配度",
              "summary": "当前样本显示双方至少能接住基本互动。",
              "bullets": ["推进感存在", "仍需更多样本确认稳定性"],
              "confidence": 0.6,
              "signal_ids": ["signal_initiative_self", "signal_warmth_other"]
            }
          ],
          "uncertainty_notes": ["样本长度有限", "缺少线下互动背景"]
        }
        """
    )

    assert isinstance(result, LLMAnalysisResult)
    assert result.summary == "这是一份偏谨慎的补充观察。"
    assert result.type_assessments[0].candidates[0].mbti_type == "ENFP"
    assert result.insights[0].section == ReportSection.RELATIONSHIP


def test_llm_analysis_adapter_builds_report_enrichment_cards() -> None:
    """It adapts typed LLM output into report-ready cards and metadata."""

    enrichment = LLMAnalysisAdapter().adapt(
        {
            "summary": "模型补充认为互动有继续观察的价值。",
            "type_assessments": [
                {
                    "subject": "other",
                    "summary": "对方可能偏内倾判断型，但不宜下定论。",
                    "confidence": 0.49,
                    "signal_ids": ["signal_planning_other"],
                    "candidates": [
                        {
                            "mbti_type": "INFJ",
                            "score": 0.38,
                            "why_like": ["更偏慢热和谨慎表达"],
                            "why_not_like": ["聊天样本不足"]
                        }
                    ],
                }
            ],
            "insights": [
                {
                    "section": "advice",
                    "title": "推进建议",
                    "summary": "更适合用具体邀约替代猜测。",
                    "bullets": ["把时间和选项说清楚"],
                    "confidence": 0.65,
                    "signal_ids": ["signal_planning_other"],
                }
            ],
            "uncertainty_notes": ["背景补充为空"],
            "metadata": {"provider": "openai"},
        }
    )

    card_types = {card.type for card in enrichment.cards}
    card_ids = {card.card_id for card in enrichment.cards}

    assert ReportCardType.CURRENT_STAGE in card_types
    assert ReportCardType.LIKELY_TYPE in card_types
    assert ReportCardType.COMMUNICATION_ADVICE in card_types
    assert ReportCardType.UNCERTAINTY in card_types
    assert "llm_type_other_0" in card_ids
    assert enrichment.metadata["provider"] == "openai"
    assert enrichment.metadata["card_count"] == 4


def test_llm_analysis_adapter_rejects_invalid_mbti_type() -> None:
    """It rejects invalid type candidates before report merging."""

    try:
        LLMAnalysisAdapter().parse(
            {
                "summary": "示例",
                "type_assessments": [
                    {
                        "subject": "self",
                        "summary": "示例",
                        "candidates": [
                            {
                                "mbti_type": "ABCD",
                                "score": 0.4,
                                "why_like": [],
                                "why_not_like": [],
                            }
                        ],
                    }
                ],
                "insights": [],
                "uncertainty_notes": [],
            }
        )
    except ValueError as exc:
        assert "canonical four-letter MBTI code" in str(exc)
        return

    raise AssertionError("expected invalid MBTI candidate to raise ValueError")
