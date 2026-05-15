"""SQLAlchemy model tests for the slice-17 tag system.

Per task 2.1 verification spec — two assertions:
(a) `Tag.__tablename__ == "tag"` and all five spec columns are present.
(b) `Meeting.tags` is a many-to-many relationship via the `meeting_tag`
    junction table.
"""

from __future__ import annotations

from meeting_playbook.meetings.models import Meeting
from meeting_playbook.tags.models import MeetingTag, Tag


def test_tag_model_table_and_columns() -> None:
    assert Tag.__tablename__ == "tag"
    column_names = {col.name for col in Tag.__table__.columns}
    assert column_names == {"id", "user_id", "name", "color", "created_at"}


def test_meeting_tag_model_table_and_columns() -> None:
    assert MeetingTag.__tablename__ == "meeting_tag"
    column_names = {col.name for col in MeetingTag.__table__.columns}
    assert column_names == {"meeting_id", "tag_id", "attached_at"}


def test_meeting_tags_relationship_through_meeting_tag_junction() -> None:
    """Meeting.tags is a many-to-many secondary'd through `meeting_tag`."""
    relationship = Meeting.__mapper__.relationships["tags"]
    secondary = relationship.secondary
    assert secondary is not None
    assert secondary.name == "meeting_tag"
