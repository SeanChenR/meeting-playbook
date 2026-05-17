"""Pydantic schemas for the playbook router.

`PlaybookUpsert` — request body for PUT. All seven content fields are
optional individually; missing fields default to the empty string per spec
(Requirement: "PUT performs a full upsert with seven content fields").

`PlaybookRead` — wire shape returned by both endpoints.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, computed_field


class PlaybookUpsert(BaseModel):
    free_form_markdown: str = ""
    objective: str = ""
    counterparty_profile: str = ""
    anticipated_topics: str = ""
    anticipated_objections: str = ""
    talking_points: str = ""
    red_lines: str = ""


class PlaybookRead(BaseModel):
    id: str
    meeting_id: str
    free_form_markdown: str
    objective: str
    counterparty_profile: str
    anticipated_topics: str
    anticipated_objections: str
    talking_points: str
    red_lines: str
    created_at: datetime
    updated_at: datetime
    # Slice-20c: `True` when the live attachment-set hash differs from the
    # snapshot captured at generation time. The UI shows a "regenerate"
    # banner when this is true.
    is_stale: bool = False
    # Slice-23: previous-version snapshot fields. Populated only after a
    # successful regenerate; user-save upserts MUST NOT touch them. The
    # frontend reads these to render the line-level diff viewer.
    previous_free_form_markdown: str | None = None
    previous_updated_at: datetime | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_previous_version(self) -> bool:
        """Derived per design D7 — single source of truth for the UI toggle.

        True iff a previous version snapshot exists. Mirrors the SQL
        predicate `previous_free_form_markdown IS NOT NULL`.
        """
        return self.previous_free_form_markdown is not None

    model_config = {"from_attributes": True}
