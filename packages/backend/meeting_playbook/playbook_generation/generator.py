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
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, TypedDict

from meeting_playbook.attachments.multimodal_context import (
    EMPTY_SET_SNAPSHOT_HASH,
    AttachmentRef,
    MultimodalContextBuilder,
)
from meeting_playbook.attachments.processor import AttachmentProcessor
from meeting_playbook.calendar.client import CalendarEvent
from meeting_playbook.config import get_settings
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


CallModel = Callable[[Any], Awaitable[str]]
"""Generic LLM dispatcher signature.

The contents payload is either a plain prompt string (text-only path,
unchanged from pre-slice-20c behaviour) or a list of google-genai
`Part` objects (slice-20c multimodal path). Production wires this via
`_default_call_model()`; tests inject mocks that accept a string in
the empty-attachments path.
"""


def _default_call_model() -> CallModel:
    """Build a CallModel wrapping the official google-genai client against Vertex AI.

    Lazy: the real client is only constructed on first call so unit tests
    (which inject a fake) never need GCP credentials configured.
    """

    async def _call(prompt: Any) -> str:
        # Local import keeps the module load-light; tests mocking the SDK
        # never exercise this path.
        from google import genai
        from google.genai import types as genai_types

        # Read from Settings, NOT os.environ — pydantic-settings loads
        # `.env` into Settings but does NOT export those values to the
        # process environment, so `os.environ.get(...)` would silently
        # fall back to defaults whenever the user configures via `.env`.
        settings = get_settings()
        client = genai.Client(
            vertexai=True,
            project=settings.vertex_ai_project,
            location=settings.vertex_ai_location,
        )

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
        attachment_refs: Sequence[AttachmentRef] = (),
    ) -> PlaybookDraft:
        """Generate a 7-field playbook draft for the given calendar event.

        Slice-20c: when `attachment_refs` is non-empty, the LLM call uses
        a multimodal `Parts` list (images as `Part.from_bytes`, extracted
        text appended to the prompt). Empty `attachment_refs` keeps the
        pre-slice path byte-identical.
        """
        primary_prompt = build_primary_prompt(event, viewer_email, viewer_name)
        primary_contents = self._wrap_with_attachments(primary_prompt, attachment_refs)
        primary_raw = await self._call_with_timeout(primary_contents)
        draft = _parse_draft(primary_raw)

        empties = _empty_fields(draft)
        if not empties:
            return draft

        fallback_prompt = build_fallback_prompt(event, empties, viewer_email, viewer_name)
        fallback_contents = self._wrap_with_attachments(fallback_prompt, attachment_refs)
        fallback_raw = await self._call_with_timeout(fallback_contents)
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

    async def _call_with_timeout(self, contents: Any) -> str:
        try:
            return await asyncio.wait_for(self._call_model(contents), timeout=self._timeout)
        except TimeoutError as exc:
            raise PlaybookGenerationTimeout(
                f"Vertex AI call exceeded {self._timeout}s deadline."
            ) from exc

    @staticmethod
    def _wrap_with_attachments(prompt: str, attachment_refs: Sequence[AttachmentRef]) -> Any:
        """Return a multimodal Parts list when attachments exist, else the plain prompt.

        Empty `attachment_refs` short-circuits with the plain prompt
        string so the pre-slice-20c call path is byte-identical.
        """
        if not attachment_refs:
            return prompt
        settings = get_settings()
        builder = MultimodalContextBuilder(
            AttachmentProcessor(
                text_extraction_timeout_seconds=(
                    settings.attachment_text_extraction_timeout_seconds
                ),
            )
        )
        context = builder.build(
            text_context=prompt,
            attachments=list(attachment_refs),
        )
        return context.parts


__all__ = [
    "CONTENT_FIELDS",
    "PlaybookDraft",
    "PlaybookGenerationFailed",
    "PlaybookGenerationTimeout",
    "PlaybookGenerator",
]
