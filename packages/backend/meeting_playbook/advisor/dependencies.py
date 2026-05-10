"""FastAPI dependency for the TacticalAdvisor.

Process-scoped singleton (memoised via `lru_cache`) so the underlying
google-genai SDK client is reused across requests. Tests can override the
dependency to inject a mock advisor; tests can also call
`get_tactical_advisor_dependency.cache_clear()` between cases when they
want a fresh process state.
"""

from __future__ import annotations

from functools import lru_cache

from meeting_playbook.advisor.base import TacticalAdvisor
from meeting_playbook.advisor.vertex_advisor import VertexFlashAdvisor
from meeting_playbook.config import get_settings


def _build_vertex_client():  # pragma: no cover — exercised at production runtime, not in tests
    """Build a real google-genai Client against Vertex AI.

    Reads `vertex_ai_project` + `vertex_ai_location` from `Settings` (which
    pydantic-settings loads from `.env`) — NOT directly from `os.environ`,
    because pydantic-settings does NOT export `.env` values into the
    process environment. Reading `os.environ` here would silently fall
    back to defaults whenever Sean configures via `.env` instead of a
    shell `export`, which is exactly the bug that produced a 404 against
    `us-central1` when `.env` had `VERTEX_AI_LOCATION=global`.

    Lazy-imports the SDK so the module loads without google-genai installed
    (test runs that mock the advisor never need GCP credentials).
    """
    from google import genai

    settings = get_settings()
    return genai.Client(
        vertexai=True,
        project=settings.vertex_ai_project,
        location=settings.vertex_ai_location,
    )


@lru_cache
def get_tactical_advisor_dependency() -> TacticalAdvisor:
    """Return a process-scoped singleton TacticalAdvisor (Vertex Flash impl)."""
    settings = get_settings()
    return VertexFlashAdvisor(
        client_factory=_build_vertex_client,
        model_id=settings.vertex_flash_model_id,
    )


__all__ = ["get_tactical_advisor_dependency"]
