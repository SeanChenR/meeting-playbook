"""FastAPI dependency for the MeetingSummarizer.

Process-scoped singleton (memoised via `lru_cache`) so the underlying
google-genai SDK client is reused across requests + the background
summary task. Tests can override the dependency to inject a mock
summarizer; tests can also call
`get_meeting_summarizer_dependency.cache_clear()` between cases when
they want a fresh process state.

Mirrors `advisor/dependencies.py` (slice-9): reads project / location
from `Settings` (which pydantic-settings loads from `.env`), NOT from
`os.environ`.
"""

from __future__ import annotations

from functools import lru_cache

from meeting_playbook.config import get_settings
from meeting_playbook.meetings.dependencies import get_session_factory_dependency
from meeting_playbook.summarization.base import MeetingSummarizer
from meeting_playbook.summarization.vertex_summarizer import VertexProSummarizer


def _build_vertex_client():  # pragma: no cover — exercised at production runtime
    """Build a real google-genai Client against Vertex AI.

    Lazy-imports the SDK so the module loads without google-genai
    installed (test runs that mock the summarizer never need GCP creds).
    """
    from google import genai

    settings = get_settings()
    return genai.Client(
        vertexai=True,
        project=settings.vertex_ai_project,
        location=settings.vertex_ai_location,
    )


@lru_cache
def get_meeting_summarizer_dependency() -> MeetingSummarizer:
    """Return a process-scoped singleton MeetingSummarizer (Vertex Pro impl)."""
    settings = get_settings()
    session_factory = get_session_factory_dependency()
    return VertexProSummarizer(
        client_factory=_build_vertex_client,
        model_id=settings.vertex_pro_model_id,
        session_factory=session_factory,
        locale="zh-TW",
    )


__all__ = ["get_meeting_summarizer_dependency"]
