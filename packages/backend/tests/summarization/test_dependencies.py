"""MeetingSummarizer FastAPI dependency — singleton behaviour."""

from __future__ import annotations

from meeting_playbook.summarization.dependencies import (
    get_meeting_summarizer_dependency,
)


def test_dependency_returns_singleton(monkeypatch):
    """Slice-10: two calls return the same MeetingSummarizer instance."""
    monkeypatch.setenv("VERTEX_AI_PROJECT", "test-project")
    monkeypatch.setenv("VERTEX_AI_LOCATION", "us-central1")

    get_meeting_summarizer_dependency.cache_clear()
    a = get_meeting_summarizer_dependency()
    b = get_meeting_summarizer_dependency()
    assert a is b
    get_meeting_summarizer_dependency.cache_clear()
