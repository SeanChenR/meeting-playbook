"""Pydantic schemas for the recording-index router (P4 IA refactor).

Per spec `recording-index` the list endpoint returns rows with the shape
`{id, meeting_id, meeting_title, counterparty_label, captured_at,
duration_ms, byte_size, stream}` paginated by `{recordings, total, page,
page_size}`.

Duration is computed from the WAV byte count divided by the canonical
16 kHz mono 16-bit PCM byte rate (32 000 bytes / second). Headers strip
the standard 44-byte RIFF envelope; over a 30-day window that's well
under one bucket of error so a closed-form division is precise enough.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RecordingStream = Literal["me", "counterparty"]


class RecordingSummary(BaseModel):
    """Single row in the `/api/recordings` response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    meeting_id: str
    meeting_title: str
    counterparty_label: str
    captured_at: datetime
    duration_ms: int
    byte_size: int
    stream: RecordingStream


class RecordingListResponse(BaseModel):
    recordings: list[RecordingSummary]
    total: int
    page: int
    page_size: int


class BatchDownloadRequest(BaseModel):
    recording_ids: list[str] = Field(min_length=1, max_length=200)
