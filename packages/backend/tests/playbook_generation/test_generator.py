"""PlaybookGenerator — Vertex AI Gemini 2.5 Pro draft generation.

Per spec slice-05-calendar-llm-playbook (playbook-generation):
- Every input event MUST yield seven non-empty content fields
- free_form_markdown MUST contain at least three lines
- Vertex AI is the ONLY allowed LLM provider; non-Vertex imports are forbidden
- Generator output shape MUST match PlaybookUpsertPayload exactly
- Sparse events trigger a fallback prompt; if fallback still empties a field,
  a localized sentinel string fills it
- Upstream timeout / parse failures raise typed exceptions
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import pytest

from meeting_playbook.calendar.client import CalendarEvent
from meeting_playbook.playbook_generation.generator import (
    PlaybookDraft,
    PlaybookGenerationFailed,
    PlaybookGenerationTimeout,
    PlaybookGenerator,
)
from meeting_playbook.playbooks.repository import _CONTENT_FIELDS, PlaybookRepository

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURE_FILES = sorted(p.name for p in FIXTURES_DIR.glob("*.json"))


def _load_event(name: str) -> CalendarEvent:
    data = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
    return CalendarEvent(
        id=data["id"],
        title=data["title"],
        start=data["start"],
        end=data["end"],
        attendees=data.get("attendees", []),
        description=data.get("description", ""),
        organizer=data.get("organizer", ""),
    )


def _good_response_json() -> str:
    """A deterministic JSON response that satisfies all seven non-empty-field assertions."""
    return json.dumps(
        {
            "free_form_markdown": "# Brief\n\n- bullet 1\n- bullet 2\n\nClosing notes.",
            "objective": "簽下 Q3 contract 並穩住客戶關係",
            "counterparty_profile": "林經理 — Director of Procurement at Acme",
            "anticipated_topics": "1. pricing\n2. timeline\n3. SLA",
            "anticipated_objections": "**budget freeze** + competitor X pricing",
            "talking_points": "1. ROI calc\n2. case study",
            "red_lines": "不得低於 30% 折扣",
        },
        ensure_ascii=False,
    )


def _bad_response_with_empty(field: str) -> str:
    full = json.loads(_good_response_json())
    full[field] = ""
    return json.dumps(full, ensure_ascii=False)


@pytest.mark.parametrize("fixture_name", FIXTURE_FILES)
@pytest.mark.asyncio
async def test_generator_produces_seven_non_empty_fields(fixture_name):
    """Every fixture must produce seven non-empty fields and free_form ≥ 3 lines."""
    event = _load_event(fixture_name)

    async def fake_call(_prompt: str) -> str:
        return _good_response_json()

    gen = PlaybookGenerator(call_model=fake_call)
    draft = await gen.generate(event, viewer_email="me@x.com", viewer_name="Me")

    # Every structured field is a non-empty trimmed string.
    for key in (
        "objective",
        "counterparty_profile",
        "anticipated_topics",
        "anticipated_objections",
        "talking_points",
        "red_lines",
    ):
        assert draft[key].strip() != "", f"{fixture_name}: {key} unexpectedly empty"

    # free_form_markdown contains at least three lines, each with at least 1 char.
    lines = [ln for ln in draft["free_form_markdown"].splitlines() if ln.strip()]
    assert len(lines) >= 3, f"{fixture_name}: free_form_markdown has fewer than 3 non-blank lines"


@pytest.mark.asyncio
async def test_generator_output_shape_matches_playbook_upsert_payload():
    """Draft keys MUST exactly match `PlaybookUpsertPayload` fields, no extras."""

    async def fake_call(_prompt: str) -> str:
        return _good_response_json()

    gen = PlaybookGenerator(call_model=fake_call)
    draft = await gen.generate(_load_event("rich.json"), viewer_email="me@x.com", viewer_name="Me")

    assert set(draft.keys()) == set(_CONTENT_FIELDS)
    for value in draft.values():
        assert isinstance(value, str)


@pytest.mark.asyncio
async def test_generator_module_does_not_import_non_vertex_providers():
    """The generator source MUST NOT reference Anthropic / OpenAI / Cohere / etc.

    A simple greppable invariant matching the spec requirement:
    "Generator uses Vertex AI Gemini 2.5 Pro through the official SDK".
    """
    from meeting_playbook.playbook_generation import generator as gen_mod

    src = Path(gen_mod.__file__).read_text(encoding="utf-8")
    forbidden = ("anthropic", "openai", "cohere", "mistral", "huggingface_hub")
    for name in forbidden:
        assert name not in src.lower(), f"forbidden provider import: {name}"


@pytest.mark.asyncio
async def test_first_call_empty_field_triggers_fallback_prompt_and_resolves():
    """Primary returns objective='' → fallback prompt is invoked → second call returns non-empty."""
    calls: list[str] = []

    async def fake_call(prompt: str) -> str:
        calls.append(prompt)
        # First call → empty objective; second call → full good response.
        if len(calls) == 1:
            return _bad_response_with_empty("objective")
        return _good_response_json()

    gen = PlaybookGenerator(call_model=fake_call)
    draft = await gen.generate(_load_event("rich.json"), viewer_email="me@x.com", viewer_name="Me")

    assert len(calls) == 2, "Expected exactly one fallback retry"
    assert "fallback" in calls[1].lower() or "missing" in calls[1].lower(), (
        "Fallback prompt should mark itself differently from the primary prompt"
    )
    assert draft["objective"].strip() != ""


@pytest.mark.asyncio
async def test_second_fallback_still_empty_inserts_sentinel_string():
    """If both calls return empty for a field, the final draft fills the
    spec-defined "(請自行填寫)" sentinel."""

    async def fake_call(_prompt: str) -> str:
        return _bad_response_with_empty("red_lines")

    gen = PlaybookGenerator(call_model=fake_call)
    draft = await gen.generate(_load_event("sparse.json"), viewer_email="me@x.com", viewer_name="Me")

    assert draft["red_lines"].strip() != ""
    assert "請自行填寫" in draft["red_lines"]


@pytest.mark.asyncio
async def test_generator_repository_round_trip(db_session):
    """A generator output MUST be directly accepted by PlaybookRepository.upsert_for_meeting."""
    from sqlalchemy import text

    # Seed a user + meeting that the playbook FK can satisfy.
    await db_session.execute(
        text(
            """
            INSERT INTO "user" (id, name, email, "emailVerified")
            VALUES ('u_round_trip', 'U', 'u_round_trip@example.com', true)
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    await db_session.execute(
        text(
            """
            INSERT INTO meeting (id, user_id, title, counterparty_display_name, me_display_name)
            VALUES ('m_round_trip', 'u_round_trip', 'T', 'C', 'M')
            """
        )
    )
    await db_session.commit()

    async def fake_call(_prompt: str) -> str:
        return _good_response_json()

    gen = PlaybookGenerator(call_model=fake_call)
    draft = await gen.generate(_load_event("rich.json"), viewer_email="me@x.com", viewer_name="Me")

    repo = PlaybookRepository(db_session)
    saved = await repo.upsert_for_meeting("m_round_trip", draft)
    for key in _CONTENT_FIELDS:
        assert getattr(saved, key) == draft[key]


@pytest.mark.asyncio
async def test_generator_timeout_raises_playbook_generation_timeout():
    async def slow_call(_prompt: str) -> str:
        await asyncio.sleep(10)  # longer than the test-injected timeout
        return _good_response_json()

    gen = PlaybookGenerator(call_model=slow_call, timeout_seconds=0.1)

    with pytest.raises(PlaybookGenerationTimeout):
        await gen.generate(_load_event("rich.json"), viewer_email="me@x.com", viewer_name="Me")


@pytest.mark.asyncio
async def test_generator_malformed_json_raises_playbook_generation_failed():
    async def bad_call(_prompt: str) -> str:
        return "this is not JSON {{{ broken"

    gen = PlaybookGenerator(call_model=bad_call)

    with pytest.raises(PlaybookGenerationFailed):
        await gen.generate(_load_event("rich.json"), viewer_email="me@x.com", viewer_name="Me")


def test_six_fixtures_present():
    """Sanity check: the 6 named fixtures from the design exist and parse."""
    expected = {"rich.json", "sparse.json", "long.json", "zh.json", "en.json", "mixed.json"}
    assert set(FIXTURE_FILES) == expected
    for name in expected:
        data = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
        assert "id" in data and "title" in data


# ─── Round-2 ingest: viewer perspective in prompt ──────────────────────────


@pytest.mark.asyncio
async def test_organizer_perspective_prompt_names_viewer_as_host():
    """Viewer email matches event.organizer_email → role label `organizer` + host guidance."""
    captured: list[str] = []

    async def capture(prompt: str) -> str:
        captured.append(prompt)
        return _good_response_json()

    event = CalendarEvent(
        id="evt_org",
        title="Q3 review",
        start="2026-05-09T10:00:00Z",
        end="2026-05-09T11:00:00Z",
        attendees=["counter@x.com"],
        description="quarterly",
        organizer="Sean",
        organizer_email="sean@example.com",
    )

    gen = PlaybookGenerator(call_model=capture)
    await gen.generate(event, viewer_email="sean@example.com", viewer_name="Sean Chen")

    assert len(captured) >= 1
    prompt = captured[0]
    assert "organizer" in prompt.lower()
    assert "Sean Chen" in prompt
    assert "sean@example.com" in prompt
    # Role-specific guidance line keyword for organizer.
    assert "hosting" in prompt.lower() or "driving" in prompt.lower()


@pytest.mark.asyncio
async def test_attendee_perspective_prompt_names_viewer_as_participant():
    """Viewer email is in attendees but NOT organizer → role label `attendee` + participant guidance."""
    captured: list[str] = []

    async def capture(prompt: str) -> str:
        captured.append(prompt)
        return _good_response_json()

    event = CalendarEvent(
        id="evt_att",
        title="Demo",
        start="2026-05-09T10:00:00Z",
        end="2026-05-09T11:00:00Z",
        attendees=["me@x.com", "host@x.com"],
        description="",
        organizer="Host",
        organizer_email="host@x.com",
    )

    gen = PlaybookGenerator(call_model=capture)
    await gen.generate(event, viewer_email="me@x.com", viewer_name="Me Person")

    prompt = captured[0]
    assert "attendee" in prompt.lower()
    assert "Me Person" in prompt
    # Participant-side guidance keywords.
    assert "invited" in prompt.lower() or "participant" in prompt.lower()


@pytest.mark.asyncio
async def test_external_perspective_prompt_names_viewer_as_observer():
    """Viewer in neither organizer nor attendees → `external` + observer guidance."""
    captured: list[str] = []

    async def capture(prompt: str) -> str:
        captured.append(prompt)
        return _good_response_json()

    event = CalendarEvent(
        id="evt_ext",
        title="實戰營 Live Session",
        start="2026-05-09T10:00:00Z",
        end="2026-05-09T11:00:00Z",
        attendees=["instructor@course.com"],
        description="",
        organizer="Course Bot",
        organizer_email="bot@course.com",
    )

    gen = PlaybookGenerator(call_model=capture)
    await gen.generate(event, viewer_email="subscriber@x.com", viewer_name="Subscriber")

    prompt = captured[0]
    assert "external" in prompt.lower()
    assert "Subscriber" in prompt
    # Observer-side guidance keywords.
    assert "subscribe" in prompt.lower() or "observ" in prompt.lower()


@pytest.mark.asyncio
async def test_empty_viewer_email_degrades_to_external_role():
    """Empty viewer_email → role classification = external; call still succeeds."""
    captured: list[str] = []

    async def capture(prompt: str) -> str:
        captured.append(prompt)
        return _good_response_json()

    event = CalendarEvent(
        id="evt_no_viewer",
        title="Whoever",
        start="2026-05-09T10:00:00Z",
        end="2026-05-09T11:00:00Z",
        attendees=["someone@x.com"],
        description="",
        organizer="Org",
        organizer_email="org@x.com",
    )

    gen = PlaybookGenerator(call_model=capture)
    draft = await gen.generate(event, viewer_email="", viewer_name="")

    assert "external" in captured[0].lower()
    # Generator still emits a valid 7-field draft.
    assert set(draft.keys()) == {
        "free_form_markdown",
        "objective",
        "counterparty_profile",
        "anticipated_topics",
        "anticipated_objections",
        "talking_points",
        "red_lines",
    }
