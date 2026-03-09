"""Thin FastAPI wrapper around the existing local analysis pipeline."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from src.analysis_pipeline import analyze_file

DEFAULT_WEB_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]
SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt"}


def create_app() -> FastAPI:
    """Create the small API app used for local frontend integration."""

    app = FastAPI(
        title="MBTI Relationship Analysis API",
        version="0.1.0",
        description=(
            "Thin FastAPI wrapper for the existing transcript analysis pipeline."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_load_web_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        """Return a simple health payload for local checks."""

        return {
            "status": "ok",
            "service": "mbti-relationship-analysis-api",
        }

    @app.post("/api/analyze")
    async def analyze_transcript(
        transcript: Annotated[UploadFile, File(...)],
        self_names: Annotated[str | None, Form()] = None,
    ) -> dict[str, object]:
        """Analyze an uploaded transcript with the existing local pipeline."""

        try:
            upload_name = _normalize_upload_name(
                filename=transcript.filename,
                content_type=transcript.content_type,
            )
            raw_bytes = await transcript.read()
        finally:
            await transcript.close()

        if not raw_bytes:
            raise HTTPException(status_code=400, detail="Uploaded transcript is empty.")

        normalized_self_names = _parse_self_names(self_names)

        try:
            with TemporaryDirectory(prefix="mbti-upload-") as temp_dir:
                temp_path = Path(temp_dir) / upload_name
                temp_path.write_bytes(raw_bytes)
                artifacts = analyze_file(
                    temp_path,
                    self_names=normalized_self_names or None,
                )
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=400,
                detail="Transcript must be UTF-8 encoded text.",
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process uploaded transcript: {exc}",
            ) from exc

        artifacts_payload = artifacts.to_dict()
        return {
            "status": "ok",
            "input": {
                "filename": upload_name,
                "content_type": transcript.content_type,
                "self_names": normalized_self_names,
            },
            "report": artifacts_payload["report"],
            "artifacts": artifacts_payload,
        }

    return app


def main() -> None:
    """Run the API with sensible local defaults."""

    import uvicorn

    uvicorn.run("src.api:app", host="127.0.0.1", port=8000, reload=False)


def _load_web_origins() -> list[str]:
    """Resolve the local frontend origins allowed by the API."""

    raw_origins = os.getenv("MBTI_WEB_ORIGINS")
    if not raw_origins:
        return list(DEFAULT_WEB_ORIGINS)

    origins = [value.strip() for value in raw_origins.split(",") if value.strip()]
    return origins or list(DEFAULT_WEB_ORIGINS)


def _normalize_upload_name(filename: str | None, content_type: str | None) -> str:
    """Return a safe upload filename while preserving parser-friendly suffixes."""

    candidate = Path(filename or "transcript").name
    stem = Path(candidate).stem or "transcript"
    suffix = Path(candidate).suffix.casefold()

    if suffix in SUPPORTED_SUFFIXES:
        return f"{stem}{suffix}"

    if suffix:
        supported_suffixes = ", ".join(sorted(SUPPORTED_SUFFIXES))
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported parser type '{suffix}'. Supported: {supported_suffixes}"
            ),
        )

    if content_type in {"text/markdown", "text/x-markdown"}:
        return f"{stem}.md"

    return f"{stem}.txt"


def _parse_self_names(raw_value: str | None) -> list[str]:
    """Parse self-name input from JSON, comma-separated, or newline-separated form."""

    if raw_value is None:
        return []

    normalized = raw_value.strip()
    if not normalized:
        return []

    if normalized.startswith("["):
        try:
            parsed = json.loads(normalized)
        except json.JSONDecodeError:
            parsed = None
        else:
            if isinstance(parsed, list):
                return _dedupe_names(str(item) for item in parsed)

    return _dedupe_names(re.split(r"[,\n，、;；]+", normalized))


def _dedupe_names(values: Iterable[str]) -> list[str]:
    """Normalize self-name values while preserving order."""

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).strip()
        if not normalized:
            continue
        dedupe_key = normalized.casefold()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        result.append(normalized)
    return result


app = create_app()


__all__ = ["app", "create_app", "main"]
