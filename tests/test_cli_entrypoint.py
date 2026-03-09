from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "tests/fixtures/flirty_positive_chat.md"


def test_run_analysis_script_executes_from_repo_root() -> None:
    """The compatibility wrapper should work without PYTHONPATH hacks."""

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_analysis.py",
            "--input",
            str(FIXTURE_PATH),
            "--self-name",
            "Me",
            "--report-only",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)

    assert payload["sections"]
    assert payload["metadata"]["llm_enrichment"]["fallback_reason"] == "disabled"
