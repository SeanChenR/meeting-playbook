"""Pydantic request / response schemas for the meetings router.

Per design.md (slice-03-meeting-crud):
- `MeetingCreate` validates that title / counterparty / me display names are
  present AND non-empty after stripping whitespace.
- `MeetingRead` is the wire shape returned by every endpoint that emits a
  meeting; it pre-allocates `started_at` and `ended_at` so future slices can
  populate them without an API change.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MeetingStatus = Literal["scheduled", "in_progress", "completed"]


class MeetingCreate(BaseModel):
    title: str = Field(min_length=1)
    counterparty_display_name: str = Field(min_length=1)
    me_display_name: str = Field(min_length=1)

    @field_validator("title", "counterparty_display_name", "me_display_name", mode="before")
    @classmethod
    def _strip_and_require(cls, v: object) -> str:
        if not isinstance(v, str):
            raise ValueError("must be a string")
        stripped = v.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class MeetingRead(BaseModel):
    id: str
    user_id: str
    title: str
    counterparty_display_name: str
    me_display_name: str
    status: MeetingStatus
    asr_provider: str
    calendar_event_id: str | None
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None

    model_config = {"from_attributes": True}
