"""FastAPI dependencies for the calendar router.

Tests override these with stubs; production wires the real CalendarClient
+ TokenStore + PlaybookGenerator (each lazily constructed).

The TokenStore is constructed with an explicit base_url + secret read from
Settings (pydantic-settings loads .env), since `os.environ` does NOT carry
those values when uvicorn is launched via `uv run` without `--env-file`.
"""

from __future__ import annotations

from functools import lru_cache

from meeting_playbook.calendar.client import CalendarClient
from meeting_playbook.calendar.token_store import TokenStore
from meeting_playbook.config import get_settings
from meeting_playbook.playbook_generation.generator import PlaybookGenerator


@lru_cache
def _token_store() -> TokenStore:
    settings = get_settings()
    return TokenStore(
        base_url=settings.backend_internal_auth_url,
        secret=settings.backend_internal_auth_secret,
    )


@lru_cache
def _calendar_client() -> CalendarClient:
    return CalendarClient(token_store=_token_store())


@lru_cache
def _playbook_generator() -> PlaybookGenerator:
    return PlaybookGenerator()


def get_calendar_client_dependency() -> CalendarClient:
    return _calendar_client()


def get_playbook_generator_dependency() -> PlaybookGenerator:
    return _playbook_generator()
