"""Pydantic schemas for the meeting_links router.

Per slice-21 design "Implementation Contract":
- `MeetingLinkView` is the join-projected shape returned by the list endpoint;
  every view is "other-meeting perspective" (the caller never sees row direction).
- `MeetingLinkCreateRequest` is the POST body shape — `to_meeting_id` is the
  only client-supplied field; the `from_meeting_id` is taken from the URL.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

MeetingLinkType = Literal["related"]


class MeetingLinkView(BaseModel):
    """Join-projected view returned by `GET /api/meetings/{id}/links`.

    `other_meeting_*` fields refer to the meeting on the OPPOSITE side of
    the observed meeting (the URL `{id}`). Repository ensures this is
    independent of which side was the original `from_meeting_id`.
    """

    model_config = ConfigDict(from_attributes=True)

    link_id: UUID
    other_meeting_id: str
    other_meeting_title: str
    other_meeting_scheduled_start_at: datetime
    link_type: MeetingLinkType
    created_at: datetime


class MeetingLinkCreateRequest(BaseModel):
    """Body of `POST /api/meetings/{id}/links`.

    `to_meeting_id` is required — Pydantic raises `ValidationError` when
    omitted, which the FastAPI 422 handler converts to a
    `common.validation_error` envelope.
    """

    to_meeting_id: str = Field(min_length=1)
