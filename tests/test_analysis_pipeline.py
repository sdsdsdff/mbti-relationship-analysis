"""Smoke tests for the end-to-end MVP analysis pipeline."""

from pathlib import Path
import json

from src.analysis_pipeline import analyze_file, write_analysis_json


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_analyze_file_smoke(tmp_path: Path) -> None:
    """It runs parse -> normalize -> extract -> report and writes JSON output."""

    artifacts = analyze_file(
        FIXTURES_DIR / "flirty_positive_chat.md",
        self_names=["Me"],
    )
    output_path = write_analysis_json(artifacts, tmp_path / "analysis.json")
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert artifacts.conversation.title == "Late Night Flirty Chat"
    assert artifacts.signal_set.signals
    assert artifacts.report.sections
    assert payload["report"]["conversation_id"] == artifacts.conversation.conversation_id
    assert payload["conversation"]["title"] == "Late Night Flirty Chat"
