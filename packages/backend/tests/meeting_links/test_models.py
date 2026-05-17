"""Model + schema tests — slice-21 task 1.2.

Three red-then-green cases:
1. SQLAlchemy `MeetingLink` model exposes the fields the migration writes.
2. `MeetingLinkView` Pydantic schema accepts a payload with UUID + datetime
   fields and round-trips them as the typed view shape.
3. `MeetingLinkCreateRequest` raises `ValidationError` when `to_meeting_id`
   is missing — protects the POST endpoint from accepting empty bodies.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from meeting_playbook.meeting_links.models import MeetingLink
from meeting_playbook.meeting_links.schemas import (
    MeetingLinkCreateRequest,
    MeetingLinkView,
)


def test_meeting_link_model_has_required_columns() -> None:
    """Model fields cover every column the migration writes."""
    cols = {c.name for c in MeetingLink.__table__.columns}
    assert {
        "id",
        "from_meeting_id",
        "to_meeting_id",
        "link_type",
        "created_at",
    }.issubset(cols), f"missing columns: {cols}"


def test_meeting_link_view_accepts_uuid_and_datetime() -> None:
    """`MeetingLinkView` round-trips a typical join row from the bidirectional query."""
    link_id = uuid4()
    other_meeting_id = "m_abc123"
    now = datetime.now()

    view = MeetingLinkView.model_validate(
        {
            "link_id": link_id,
            "other_meeting_id": other_meeting_id,
            "other_meeting_title": "Q3 review with Acme",
            "other_meeting_scheduled_start_at": now,
            "link_type": "related",
            "created_at": now,
        }
    )

    assert str(view.link_id) == str(link_id)
    assert view.other_meeting_id == other_meeting_id
    assert view.other_meeting_title == "Q3 review with Acme"
    assert view.link_type == "related"


def test_meeting_link_create_request_requires_to_meeting_id() -> None:
    """An empty body MUST fail validation — protects the POST endpoint."""
    with pytest.raises(ValidationError):
        MeetingLinkCreateRequest.model_validate({})


def test_meeting_link_create_request_accepts_string_meeting_id() -> None:
    """A valid body parses cleanly when `to_meeting_id` is provided."""
    body = MeetingLinkCreateRequest.model_validate({"to_meeting_id": "m_xyz789"})
    assert body.to_meeting_id == "m_xyz789"
