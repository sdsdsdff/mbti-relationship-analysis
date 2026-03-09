#!/usr/bin/env python3
"""Run the local MVP analysis pipeline for one transcript file."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.analysis_pipeline import analyze_file, write_analysis_json


def build_parser() -> argparse.ArgumentParser:
    """Create the small CLI parser used by the MVP script."""

    parser = argparse.ArgumentParser(description="Run MBTI relationship MVP analysis")
    parser.add_argument("--input", required=True, help="Path to the transcript file")
    parser.add_argument("--config", help="Optional path to the JSON config file")
    parser.add_argument(
        "--self-name",
        action="append",
        dest="self_names",
        default=[],
        help="Speaker alias that should be treated as self; repeatable",
    )
    parser.add_argument("--output", help="Optional output JSON path")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Write only the final report JSON instead of the full pipeline bundle",
    )
    return parser


def main() -> int:
    """Parse CLI arguments, run analysis, and print or write JSON."""

    args = build_parser().parse_args()
    artifacts = analyze_file(
        Path(args.input),
        self_names=args.self_names or None,
        config_path=args.config,
    )

    if args.output:
        output_path = write_analysis_json(
            artifacts,
            args.output,
            report_only=args.report_only,
        )
        print(f"Wrote analysis JSON to {output_path}")
        return 0

    payload = artifacts.report_json() if args.report_only else artifacts.to_json()
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
