"""TacticalAdvisor FastAPI dependency — singleton behaviour."""

from __future__ import annotations

from meeting_playbook.advisor.dependencies import get_tactical_advisor_dependency


def test_dependency_returns_singleton(monkeypatch):
    """Slice-08: two calls return the same TacticalAdvisor instance."""
    # Avoid touching the real Vertex SDK at construction time.
    monkeypatch.setenv("VERTEX_AI_PROJECT", "test-project")
    monkeypatch.setenv("VERTEX_AI_LOCATION", "us-central1")

    get_tactical_advisor_dependency.cache_clear()
    a = get_tactical_advisor_dependency()
    b = get_tactical_advisor_dependency()
    assert a is b
    get_tactical_advisor_dependency.cache_clear()
