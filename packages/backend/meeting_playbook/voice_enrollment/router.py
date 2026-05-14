"""FastAPI router for `POST /api/voice_enrollment`.

Slice-13 spec requirement "POST /api/voice_enrollment uploads + replaces
the per-user enrollment":

- Accepts multipart/form-data with one audio field.
- Validates content-type (audio/wav), size (≤ 5MB), duration (≤ 30s).
- Persists the WAV under `VOICE_ENROLLMENT_DIR/{user_id}.wav`, runs
  `compute_enrollment_embedding`, upserts the row.
- Returns HTTP 200 with `{enrolled_at}` on success.
- Returns HTTP 422 with an `error_code` (`voice_enrollment.unsupported_format`
  / `too_large` / `too_long` / `invalid_sample`) on validation failure AND
  removes the staged WAV from disk so partial uploads do not accumulate.
"""

from __future__ import annotations

import contextlib
import io
import logging
import wave
from pathlib import Path
from typing import Annotated

import anyio.to_thread
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.config import get_settings
from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_user_id_dependency,
)
from meeting_playbook.voice_enrollment.embedding import (
    InvalidEnrollmentSample,
    compute_enrollment_embedding,
)
from meeting_playbook.voice_enrollment.repository import VoiceEnrollmentRepository


logger = logging.getLogger(__name__)
router = APIRouter()


# Slice-13 design decision "30 秒上限與檔案驗證":
_MAX_SAMPLE_BYTES = 5 * 1024 * 1024  # 5 MB
_MAX_SAMPLE_DURATION_SECONDS = 30
_ACCEPTED_CONTENT_TYPES: frozenset[str] = frozenset(
    {"audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"}
)


def _voice_enrollment_dir() -> Path:
    """Resolve `VOICE_ENROLLMENT_DIR` to an absolute path with `~` expanded."""
    settings = get_settings()
    return Path(settings.voice_enrollment_dir).expanduser().resolve()


def _http_422(error_code: str, message: str) -> HTTPException:
    # `HTTP_422_UNPROCESSABLE_ENTITY` was renamed to `HTTP_422_UNPROCESSABLE_CONTENT`
    # in starlette to match the IETF RFC 9110 wording change. Both expose the
    # same numeric 422, but the old alias emits a DeprecationWarning at use
    # site — keep our code on the new name.
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={"error_code": error_code, "message": message},
    )


def _wav_duration_seconds(wav_bytes: bytes) -> float:
    """Return the duration of a WAV file in seconds.

    Uses the stdlib `wave` module so we don't pay for ffmpeg in the happy
    path; any WAV malformedness (unsupported codec, broken header, etc.)
    raises `wave.Error` which the caller surfaces as
    `voice_enrollment.unsupported_format`.
    """
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        if rate <= 0:
            raise wave.Error("WAV reports sample rate <= 0")
        return frames / float(rate)


@router.get("/api/voice_enrollment", status_code=status.HTTP_200_OK)
async def get_voice_enrollment(
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> dict[str, str | None]:
    """Return the current user's enrollment status.

    Never 404s: the empty-state body `{"enrolled_at": null}` is the canonical
    "no enrollment yet" signal so the frontend renders the saved-vs-idle
    distinction without juggling a not-found error.
    """
    repo = VoiceEnrollmentRepository(session)
    row = await repo.get_for_user(user_id)
    return {"enrolled_at": row.created_at.isoformat() if row else None}


@router.post("/api/voice_enrollment", status_code=status.HTTP_200_OK)
async def upload_voice_enrollment(
    file: UploadFile,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> dict[str, str]:
    """Accept a 30-second WAV, store it, compute the embedding, upsert
    the per-user enrollment row.
    """
    # ── 1. Content-type validation ──────────────────────────────────────
    content_type = (file.content_type or "").lower().split(";")[0].strip()
    if content_type not in _ACCEPTED_CONTENT_TYPES:
        raise _http_422(
            "voice_enrollment.unsupported_format",
            f"Expected audio/wav; received content-type={file.content_type!r}",
        )

    # ── 2. Read body + size check ───────────────────────────────────────
    body = await file.read()
    if len(body) == 0:
        raise _http_422(
            "voice_enrollment.unsupported_format",
            "Uploaded file is empty.",
        )
    if len(body) > _MAX_SAMPLE_BYTES:
        raise _http_422(
            "voice_enrollment.too_large",
            f"Sample exceeds 5MB limit (got {len(body)} bytes).",
        )

    # ── 3. Duration check via stdlib wave ───────────────────────────────
    # `wave.open` does blocking I/O on the underlying BytesIO; offload to a
    # worker thread so concurrent uploads don't stall the FastAPI event loop.
    try:
        duration_s = await anyio.to_thread.run_sync(_wav_duration_seconds, body)
    except (wave.Error, EOFError) as exc:
        raise _http_422(
            "voice_enrollment.unsupported_format",
            f"WAV header could not be parsed: {exc}",
        ) from None
    if duration_s > _MAX_SAMPLE_DURATION_SECONDS:
        raise _http_422(
            "voice_enrollment.too_long",
            f"Sample is {duration_s:.1f}s; the 30-second maximum was exceeded.",
        )

    # ── 4. Persist file under VOICE_ENROLLMENT_DIR ──────────────────────
    # Defense-in-depth: even though `user_id` comes from the auth gateway via
    # `X-User-Id`, sanitize the filename component so a compromised gateway or
    # mis-injected header can never resolve outside the enrollment directory
    # (e.g. `../../etc/passwd`). `Path(...).name` strips any directory pieces.
    enrollment_dir = _voice_enrollment_dir()
    enrollment_dir.mkdir(parents=True, exist_ok=True)
    safe_user_id = Path(user_id).name
    if not safe_user_id:
        raise _http_422(
            "voice_enrollment.unsupported_format",
            "user_id is empty after path sanitization; cannot derive WAV filename.",
        )
    wav_path = enrollment_dir / f"{safe_user_id}.wav"
    await anyio.to_thread.run_sync(wav_path.write_bytes, body)

    # ── 5. Compute embedding + upsert (with cleanup on failure) ─────────
    try:
        try:
            # Pyannote inference is heavy (~10–30s first time including
            # model load). Run in a worker thread so other API requests
            # served by the same event loop keep responding.
            embedding = await anyio.to_thread.run_sync(compute_enrollment_embedding, wav_path)
        except InvalidEnrollmentSample as exc:
            raise _http_422("voice_enrollment.invalid_sample", str(exc)) from exc

        repo = VoiceEnrollmentRepository(session)
        row = await repo.upsert(
            user_id=user_id,
            sample_wav_path=str(wav_path),
            embedding=embedding,
        )
    except HTTPException:
        # Clean up the orphan WAV so we don't accumulate failed-upload files.
        with contextlib.suppress(OSError):
            wav_path.unlink()
        raise
    except Exception:
        # Any unexpected exception still cleans up before propagating.
        with contextlib.suppress(OSError):
            wav_path.unlink()
        raise

    logger.info(
        "voice_enrollment_saved",
        extra={
            "user_id": user_id,
            "embedding_bytes": len(embedding),
            "wav_path": str(wav_path),
        },
    )
    return {"enrolled_at": row.created_at.isoformat()}
