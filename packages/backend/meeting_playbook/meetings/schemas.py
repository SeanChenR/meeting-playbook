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

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MeetingStatus = Literal["scheduled", "in_progress", "completed"]


class MeetingCreate(BaseModel):
    title: str = Field(min_length=1)
    counterparty_display_name: str = Field(min_length=1)
    me_display_name: str = Field(min_length=1)
    # Slice-15: scheduled_start_at became required for new meetings so the
    # list / kanban / calendar views can drop their `?? created_at` fallback.
    # `scheduled_end_at` remains optional; if provided it MUST be >=
    # `scheduled_start_at` (enforced in `_validate_time_range` below).
    scheduled_start_at: datetime
    scheduled_end_at: datetime | None = None

    @field_validator("title", "counterparty_display_name", "me_display_name", mode="before")
    @classmethod
    def _strip_and_require(cls, v: object) -> str:
        if not isinstance(v, str):
            raise ValueError("must be a string")
        stripped = v.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @model_validator(mode="after")
    def _validate_time_range(self) -> MeetingCreate:
        if self.scheduled_end_at is not None and self.scheduled_end_at < self.scheduled_start_at:
            raise ValueError("scheduled_end_at must be >= scheduled_start_at")
        return self


class TagSummary(BaseModel):
    """Slice-17: minimal tag payload nested inside meeting list / detail."""

    id: str
    name: str
    color: str

    model_config = {"from_attributes": True}


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
    # Slice-15: scheduled_start_at is now NOT NULL at the DB layer
    # (migration 0012 back-filled pre-existing NULL rows from created_at).
    scheduled_start_at: datetime
    scheduled_end_at: datetime | None
    # Slice-17: every list / detail payload carries the meeting's tags.
    # Defaults to empty list so legacy code paths that build MeetingRead from
    # plain dicts (no tag relationship loaded) still serialize cleanly.
    tags: list[TagSummary] = []

    model_config = {"from_attributes": True}


class MeetingPatch(BaseModel):
    """Slice-15 partial-update body.

    All fields are optional — clients send only the keys they want to
    change. Empty `{}` is accepted and treated as a no-op by the router.
    String fields reuse `MeetingCreate._strip_and_require` semantics:
    whitespace is stripped, and `""` after strip is rejected with 422.
    Cross-field rule: if BOTH `scheduled_start_at` and `scheduled_end_at`
    are present in the same body, `scheduled_end_at >= scheduled_start_at`
    MUST hold. (When only one of the two is sent, the router merges it
    with the persisted row for the cross-field check.)
    """

    title: str | None = Field(default=None, min_length=1)
    counterparty_display_name: str | None = Field(default=None, min_length=1)
    me_display_name: str | None = Field(default=None, min_length=1)
    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None
    asr_provider: str | None = Field(default=None, min_length=1)

    @field_validator(
        "title",
        "counterparty_display_name",
        "me_display_name",
        "asr_provider",
        mode="before",
    )
    @classmethod
    def _strip_and_require_if_present(cls, v: object) -> object:
        # Optional fields stay None when the client omits the key; only
        # apply the strip + non-empty rule when the value is provided.
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("must be a string")
        stripped = v.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @model_validator(mode="after")
    def _validate_time_range_within_body(self) -> MeetingPatch:
        if (
            self.scheduled_start_at is not None
            and self.scheduled_end_at is not None
            and self.scheduled_end_at < self.scheduled_start_at
        ):
            raise ValueError("scheduled_end_at must be >= scheduled_start_at")
        return self

    def as_update_fields(self) -> dict[str, object]:
        """Return the non-None fields as a dict ready for
        `MeetingRepository.update_for_user(fields=...)`. Empty dict when
        the caller sent an empty body (router treats as no-op).
        """
        return {k: v for k, v in self.model_dump().items() if v is not None}


class RecordingSummary(BaseModel):
    """Slice-16: minimal recording row shape the mini-player needs to
    locate + anchor playback.

    Just the fields a frontend audio player cares about — `id` for URL
    construction, `stream` to pick me vs counterparty, `started_at` as
    the wall-clock anchor for chunk-seek math, `deleted_at` to gate
    the play affordance behind retention.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    meeting_id: str
    stream: str
    started_at: datetime
    deleted_at: datetime | None


class MeetingDetailRead(MeetingRead):
    """Single-meeting GET response — adds slice-11 derived flags.

    Per spec meeting-management ADDED requirement
    "GET /api/meetings/{id} returns recordings_available and rerun_asr_pending
    derived fields": both flags are required booleans, computed server-side
    on every request (NOT persisted on the meeting row).

    `recordings_available`: at least one recording row has `deleted_at IS NULL`.
    `rerun_asr_pending`: the in-flight rerun registry reports the meeting.
    `recordings` (slice-16): the meeting's recording rows in a shape suitable
    for the mini-player to construct `/api/.../recordings/<id>/audio` URLs.
    """

    recordings_available: bool
    rerun_asr_pending: bool
    recordings: list[RecordingSummary] = []
