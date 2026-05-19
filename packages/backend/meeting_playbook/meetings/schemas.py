"""Pydantic request / response schemas for the meetings router.

Per design.md (slice-03-meeting-crud):
- `MeetingCreate` validates that title / counterparty / me display names are
  present AND non-empty after stripping whitespace.
- `MeetingRead` is the wire shape returned by every endpoint that emits a
  meeting; it pre-allocates `started_at` and `ended_at` so future slices can
  populate them without an API change.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

MeetingStatus = Literal["scheduled", "in_progress", "completed"]

# Derived lifecycle bucket exposed in every meeting response. Frontend renders
# this directly as the card chip + the Kanban column key (replacing the prior
# frontend-side getMeetingDateBucket time math). Status alone could not
# express "scheduled meeting whose scheduled_start_at is in the past" without
# a wall-clock comparison the client can't trust to be synchronized.
MeetingBucket = Literal["upcoming", "needs_recording", "completed"]


def _compute_bucket(status: str, scheduled_start_at: datetime, now: datetime) -> MeetingBucket:
    """Map a meeting row to its lifecycle bucket.

    Rules (locked with frontend `meetings-bucket.ts` for parity):
      - in_progress | completed → 'completed'
      - scheduled with future scheduled_start_at → 'upcoming'
      - scheduled with past scheduled_start_at  → 'needs_recording'
    """
    if status in ("in_progress", "completed"):
        return "completed"
    # Defensive: scheduled_start_at may be tz-naive on legacy rows. Treat as
    # UTC so the comparison with `now` (also UTC) doesn't raise.
    anchor = scheduled_start_at
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=UTC)
    return "upcoming" if anchor >= now else "needs_recording"


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
    # Slice-20b: `calendar_event_id` flips the request from "manual create"
    # to "calendar import create + Playbook generation". When non-null, the
    # router fetches the event detail and synchronously runs the generator
    # (matches the deprecated `POST /api/meetings/from-calendar` contract,
    # now collapsed into this single create entry point per design doc
    # `Endpoint 拆分`).
    calendar_event_id: str | None = None
    # Slice-20b: `attachments[]` carries the attachment ids the user
    # selected on the preview form. Empty list = create no attachment
    # links. Non-empty list = the router rewrites each attachment row's
    # `meeting_id` to the new meeting id within the same transaction
    # (per spec `POST /api/meetings accepts an attachments list`).
    attachments: list[str] = Field(default_factory=list)
    # Slice-21: `links[]` lets the create form pre-attach related
    # meetings without a second round-trip. Each id MUST reference an
    # existing meeting owned by the current user; the router inserts one
    # `meeting_link` row per id (de-duped) inside the same transaction
    # as the meeting create. Failure on any id aborts the whole request.
    links: list[str] = Field(default_factory=list)

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

    @computed_field
    @property
    def bucket(self) -> MeetingBucket:
        """Lifecycle bucket — `upcoming` / `needs_recording` / `completed`.

        Computed at serialization time from `status` + `scheduled_start_at`
        compared against the current UTC wall clock. Tests that need
        deterministic bucket values can construct MeetingRead via
        `model_validate` with a fixture meeting + freeze time, or build
        the response dict by hand and call `MeetingRead.model_validate`.
        """
        return _compute_bucket(self.status, self.scheduled_start_at, datetime.now(UTC))


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
