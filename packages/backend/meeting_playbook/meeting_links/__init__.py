"""Meeting linking — slice-21 manual related-meetings linking.

Public surface (deep module):
- :class:`MeetingLink` — SQLAlchemy model for the `meeting_link` row.
- :class:`MeetingLinkView` — Pydantic view used by the bidirectional list endpoint.
- :class:`MeetingLinkCreateRequest` — Pydantic body for ``POST /api/meetings/{id}/links``.
- :class:`MeetingLinkRepository` — bidirectional list/create/delete hiding row direction.
- :class:`MeetingLinkDuplicate`, :class:`MeetingLinkSelfReference` — domain exceptions.
- ``router`` — FastAPI router mounted under ``/api/meetings/{id}/links``.
"""

from meeting_playbook.meeting_links.models import MeetingLink
from meeting_playbook.meeting_links.repository import (
    MeetingLinkDuplicate,
    MeetingLinkRepository,
    MeetingLinkSelfReference,
)
from meeting_playbook.meeting_links.schemas import (
    MeetingLinkCreateRequest,
    MeetingLinkView,
)

__all__ = [
    "MeetingLink",
    "MeetingLinkCreateRequest",
    "MeetingLinkDuplicate",
    "MeetingLinkRepository",
    "MeetingLinkSelfReference",
    "MeetingLinkView",
]
