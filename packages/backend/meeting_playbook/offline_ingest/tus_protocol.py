"""Tus 1.0 resumable-upload protocol handler.

Implements the four HTTP verbs required by tus 1.0 core + the `creation`
and `termination` extensions, scoped to one upload-session-per-meeting
under `/api/meetings/{id}/recordings/offline_upload`.

Sessions are tracked in an in-memory `dict[upload_id, TusSession]` so a
backend restart drops all in-flight uploads — acceptable per the design
trade-off (individual single-machine use; user can resume by re-selecting
the file).

See `openspec/specs/offline-ingest/spec.md` for the normative contract
and `openspec/changes/slice-14-offline-ingest/design.md` Decision 2 for
the architectural rationale.
"""

from __future__ import annotations

import base64
import logging
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


_TUS_RESUMABLE_VERSION = "1.0.0"
_TUS_EXTENSIONS = "creation,termination"

# Per spec: allowed audio mimetypes accepted by tus creation. Keep as a
# frozenset so callers cannot mutate it accidentally. Browsers do not all
# agree on a single mimetype per extension (Safari + macOS Chrome serve
# `.m4a` as `audio/x-m4a`; Firefox sometimes sends an empty type for
# .flac / .ogg) so we accept the canonical RFC types AND the vendor
# variants we have actually observed in the field.
ALLOWED_MIMETYPES: frozenset[str] = frozenset(
    {
        "audio/wav",
        "audio/wave",
        "audio/x-wav",
        "audio/mpeg",
        "audio/mp3",
        "audio/mp4",
        "audio/x-m4a",
        "audio/m4a",
        "audio/aac",
        "audio/x-aac",
        "audio/flac",
        "audio/x-flac",
        "audio/ogg",
        "audio/x-ogg",
        "application/ogg",
    }
)


# Extension-based fallback for browsers / clients that omit a useful
# mimetype. The filename comes from the user's local filesystem and is
# always carried in `Upload-Metadata.filename`.
_ALLOWED_EXTENSIONS: frozenset[str] = frozenset(
    {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".oga"}
)


@dataclass
class TusSession:
    """In-memory record of one resumable upload session."""

    upload_id: str
    meeting_id: str
    user_id: str
    upload_length: int
    current_offset: int
    metadata: dict[str, str]
    staging_path: Path
    actual_started_at: datetime
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# Process-scoped session map, keyed by `upload_id`. The handlers below
# read + mutate this; tests reset it via `reset_sessions()`.
_sessions: dict[str, TusSession] = {}


def reset_sessions() -> None:
    """Drop all in-memory tus sessions.

    Used by tests to keep one test's session map from leaking into the next.
    Not exported for production use — sessions are expected to terminate
    naturally via PATCH completion or DELETE (termination extension).
    """
    _sessions.clear()


def get_session(upload_id: str) -> TusSession | None:
    """Look up a session by id; returns None when not found."""
    return _sessions.get(upload_id)


def register_session(session: TusSession) -> None:
    """Store a freshly created session, keyed by `upload_id`."""
    _sessions[session.upload_id] = session


def drop_session(upload_id: str) -> None:
    """Remove a session from the map (idempotent)."""
    _sessions.pop(upload_id, None)


# Completion hook — invoked when the final PATCH brings the staging file
# size up to `upload_length`. Wired by `offline_ingest.pipeline` at module
# import time; tests substitute a stub via `set_completion_handler`. Kept
# as a module-level callable (vs a hard import) so tus_protocol stays
# import-clean for the unit-test layer that should not pull in pipeline /
# ASR machinery.
from collections.abc import (  # noqa: E402 — intentional late import, see comment above
    Awaitable,
    Callable,
)

CompletionHandler = Callable[[TusSession], Awaitable[None]]

_completion_handler: CompletionHandler | None = None


def set_completion_handler(handler: CompletionHandler | None) -> None:
    """Install (or clear with `None`) the post-completion pipeline trigger."""
    global _completion_handler
    _completion_handler = handler


async def invoke_completion_handler(session: TusSession) -> None:
    """Invoke the registered completion handler, if any.

    Routes call this once `current_offset == upload_length`. When no
    handler is installed (pipeline module not yet imported), the call is
    a no-op so the upload still succeeds at the HTTP layer — the ASR step
    can be picked up later by a manual re-trigger.
    """
    if _completion_handler is None:
        logger.warning(
            "tus_completion_no_handler",
            extra={"upload_id": session.upload_id, "meeting_id": session.meeting_id},
        )
        return
    await _completion_handler(session)


class TusValidationError(Exception):
    """Raised by `validate_creation_metadata` on any rejection path.

    Carries the HTTP status code and project `error_code` so the FastAPI
    handler can translate to the canonical `{error_code, message}` envelope
    without re-implementing the policy table.
    """

    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message


def validate_creation_metadata(
    *,
    upload_length: int,
    metadata: dict[str, str],
    max_bytes: int,
    now: datetime,
) -> datetime:
    """Run the four spec-mandated checks before any session is created.

    Returns the parsed `actual_started_at` datetime so the caller can store
    it on the new `TusSession`. Raises `TusValidationError` with the
    matching status code + error_code on the first failure encountered.
    """
    if upload_length > max_bytes:
        raise TusValidationError(
            status_code=413,
            error_code="offline_ingest.too_large",
            message=(
                f"Upload-Length {upload_length} exceeds the configured "
                f"OFFLINE_UPLOAD_MAX_BYTES ({max_bytes})."
            ),
        )

    mimetype = metadata.get("mimetype", "").lower()
    filename = metadata.get("filename", "")
    extension = ""
    if "." in filename:
        extension = "." + filename.rsplit(".", 1)[-1].lower()

    mimetype_ok = mimetype in ALLOWED_MIMETYPES
    extension_ok = extension in _ALLOWED_EXTENSIONS

    # Accept if either the browser-supplied mimetype OR the filename
    # extension matches — covers the common case where macOS Chrome /
    # Safari serves `.m4a` as `audio/x-m4a` or `application/octet-stream`
    # while still rejecting `mimetype=video/mp4` regardless of extension.
    if not mimetype_ok and not extension_ok:
        raise TusValidationError(
            status_code=422,
            error_code="offline_ingest.unsupported_format",
            message=(
                f"mimetype {mimetype!r} / extension {extension!r} is not in "
                f"the allowed set (mimetypes: {sorted(ALLOWED_MIMETYPES)}, "
                f"extensions: {sorted(_ALLOWED_EXTENSIONS)})."
            ),
        )

    raw_started_at = metadata.get("actual_started_at", "")
    try:
        # `fromisoformat` accepts both naive and aware ISO 8601 strings —
        # treat naive as UTC so comparisons against `now` (aware) work.
        parsed = datetime.fromisoformat(raw_started_at)
    except ValueError as exc:
        raise TusValidationError(
            status_code=422,
            error_code="offline_ingest.invalid_started_at",
            message=(f"actual_started_at must be ISO 8601; got {raw_started_at!r} ({exc})."),
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    if parsed > now:
        raise TusValidationError(
            status_code=422,
            error_code="offline_ingest.invalid_started_at",
            message=(
                "actual_started_at is in the future; it must be at or "
                "before the current server time."
            ),
        )

    return parsed


def tus_capability_headers(max_bytes: int) -> dict[str, str]:
    """Headers advertised by OPTIONS so tus-js-client discovers our spec
    support before opening a session. Centralised here so the OPTIONS
    handler stays a 4-line response builder.
    """
    return {
        "Tus-Resumable": _TUS_RESUMABLE_VERSION,
        "Tus-Version": _TUS_RESUMABLE_VERSION,
        "Tus-Max-Size": str(max_bytes),
        "Tus-Extension": _TUS_EXTENSIONS,
    }


def decode_upload_metadata(header_value: str) -> dict[str, str]:
    """Parse the tus 1.0 `Upload-Metadata` header into a dict.

    The header is `key1 b64value1,key2 b64value2,...` where each value is
    base64(utf-8 bytes). Keys without a value are stored as the empty
    string. Malformed pairs are skipped so a single bad entry does not
    erase the rest of the metadata.
    """
    result: dict[str, str] = {}
    if not header_value:
        return result
    for pair in header_value.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if " " in pair:
            key, b64 = pair.split(" ", 1)
            key = key.strip()
            if not key:
                continue
            try:
                value = base64.b64decode(b64.strip(), validate=True).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                logger.warning("tus_metadata_decode_failed", extra={"key": key})
                continue
            result[key] = value
        else:
            result[pair] = ""
    return result


def new_upload_id() -> str:
    """Cryptographically random session id used in the `Location` URL."""
    return secrets.token_urlsafe(16)
