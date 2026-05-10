"""PlaybookGenerator — calls Vertex AI Gemini 2.5 Pro and emits a 7-field draft.

Per slice-05 design (playbook-generation spec):
- Returns a PlaybookDraft whose keys exactly match PlaybookUpsertPayload
- Two-stage prompt: primary, then fallback for any empty field
- After fallback, any still-empty field is filled with the EMPTY_FIELD_SENTINEL
- Vertex AI is the only provider; non-Vertex imports are forbidden in this module
- Timeout (default 60s) raises PlaybookGenerationTimeout
- JSON-parse / schema-mismatch raises PlaybookGenerationFailed
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from typing import TypedDict

from meeting_playbook.calendar.client import CalendarEvent
from meeting_playbook.playbook_generation.prompts import (
    EMPTY_FIELD_SENTINEL,
    build_fallback_prompt,
    build_primary_prompt,
)

CONTENT_FIELDS = (
    "free_form_markdown",
    "objective",
    "counterparty_profile",
    "anticipated_topics",
    "anticipated_objections",
    "talking_points",
    "red_lines",
)


class PlaybookDraft(TypedDict):
    free_form_markdown: str
    objective: str
    counterparty_profile: str
    anticipated_topics: str
    anticipated_objections: str
    talking_points: str
    red_lines: str


class PlaybookGenerationTimeout(Exception):
    """Raised when the upstream model call exceeds the configured deadline."""


class PlaybookGenerationFailed(Exception):
    """Raised when the upstream returned a response we cannot parse / validate."""


CallModel = Callable[[str], Awaitable[str]]


def _default_call_model() -> CallModel:
    """Build a CallModel wrapping the official google-genai client against Vertex AI.

    Lazy: the real client is only constructed on first call so unit tests
    (which inject a fake) never need GCP credentials configured.
    """

    async def _call(prompt: str) -> str:
        # Local import keeps the module load-light; tests mocking the SDK
        # never exercise this path.
        from google import genai
        from google.genai import types as genai_types

        project = os.environ.get("VERTEX_AI_PROJECT", "")
        location = os.environ.get("VERTEX_AI_LOCATION", "us-central1")
        client = genai.Client(vertexai=True, project=project, location=location)

        response_schema = {
            "type": "object",
            "properties": {field: {"type": "string"} for field in CONTENT_FIELDS},
            "required": list(CONTENT_FIELDS),
        }

        config = genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
        )

        # The SDK call is sync — run it on a worker thread.
        def _sync_call() -> str:
            response = client.models.generate_content(
                model="gemini-2.5-pro",
                contents=prompt,
                config=config,
            )
            return response.text or ""

        return await asyncio.to_thread(_sync_call)

    return _call


def _parse_draft(raw: str) -> PlaybookDraft:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PlaybookGenerationFailed(f"Could not parse model response as JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise PlaybookGenerationFailed("Model response was not a JSON object.")

    missing_keys = set(CONTENT_FIELDS) - set(data.keys())
    if missing_keys:
        raise PlaybookGenerationFailed(
            f"Model response is missing required keys: {sorted(missing_keys)}"
        )

    extra_keys = set(data.keys()) - set(CONTENT_FIELDS)
    if extra_keys:
        # Drop extras silently — schema enforcement on the SDK side already covers
        # the common case; we keep the strict shape on output.
        for k in extra_keys:
            data.pop(k, None)

    for k in CONTENT_FIELDS:
        if not isinstance(data[k], str):
            raise PlaybookGenerationFailed(f"Model response field {k} is not a string.")

    return PlaybookDraft(**{k: data[k] for k in CONTENT_FIELDS})  # type: ignore[typeddict-item]


def _empty_fields(draft: PlaybookDraft) -> list[str]:
    """Return the list of content fields whose value is empty after trimming."""
    out: list[str] = []
    for field in CONTENT_FIELDS:
        value = draft[field]  # type: ignore[literal-required]
        if not isinstance(value, str) or not value.strip():
            out.append(field)
            continue
        if field == "free_form_markdown":
            non_blank = [ln for ln in value.splitlines() if ln.strip()]
            if len(non_blank) < 3:
                out.append(field)
    return out


class PlaybookGenerator:
    """Two-stage Gemini 2.5 Pro draft generator with sentinel fallback.

    Args:
        call_model: An async function that takes a prompt string and returns the
            model's raw text. Defaults to the production Vertex AI wrapper.
        timeout_seconds: Per-call timeout; the spec mandates 60s in production.
            Tests inject a small value to exercise the timeout path.
    """

    def __init__(
        self,
        *,
        call_model: CallModel | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._call_model = call_model or _default_call_model()
        self._timeout = timeout_seconds

    async def generate(
        self,
        event: CalendarEvent,
        *,
        viewer_email: str,
        viewer_name: str,
    ) -> PlaybookDraft:
        primary_prompt = build_primary_prompt(event, viewer_email, viewer_name)
        primary_raw = await self._call_with_timeout(primary_prompt)
        draft = _parse_draft(primary_raw)

        empties = _empty_fields(draft)
        if not empties:
            return draft

        fallback_prompt = build_fallback_prompt(event, empties, viewer_email, viewer_name)
        fallback_raw = await self._call_with_timeout(fallback_prompt)
        fallback_draft = _parse_draft(fallback_raw)

        # Merge: prefer the fallback value for fields that were empty;
        # keep the primary value for fields that were already populated.
        merged: dict[str, str] = dict(draft)  # type: ignore[arg-type]
        for field in empties:
            merged[field] = fallback_draft[field]  # type: ignore[literal-required]

        # If any field is STILL empty after the fallback, sentinel it.
        final_empties = _empty_fields(PlaybookDraft(**merged))  # type: ignore[arg-type]
        for field in final_empties:
            merged[field] = (
                EMPTY_FIELD_SENTINEL
                if field != "free_form_markdown"
                else f"{EMPTY_FIELD_SENTINEL}\n\n（the model could not produce content for this section）\n（請於編輯器補上）"
            )

        return PlaybookDraft(**merged)  # type: ignore[arg-type]

    async def _call_with_timeout(self, prompt: str) -> str:
        try:
            return await asyncio.wait_for(self._call_model(prompt), timeout=self._timeout)
        except TimeoutError as exc:
            raise PlaybookGenerationTimeout(
                f"Vertex AI call exceeded {self._timeout}s deadline."
            ) from exc


__all__ = [
    "CONTENT_FIELDS",
    "PlaybookDraft",
    "PlaybookGenerationFailed",
    "PlaybookGenerationTimeout",
    "PlaybookGenerator",
]
