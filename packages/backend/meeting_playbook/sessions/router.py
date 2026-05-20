"""WebSocket router — /api/meetings/{id}/session.

Slice-07 evolution: opens TWO capture streams (me + counterparty) via the
dual-stream capture factory. Pre-flight rejects the session with
`session.no_blackhole_device` when BlackHole is missing. Two ASRProviders
are warmed up in parallel before the first chunk arrives. Per-stream
failures during the session are handled inside SessionService and surface
as `stream_stopped` frames.

Per design.md (`Pre-flight check: device-exists only (relaxed)`,
`Failure isolation: partial fault tolerance during in_progress`).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import AsyncExitStack
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from meeting_playbook.advisor.base import TacticalAdvisor
from meeting_playbook.advisor.dependencies import get_tactical_advisor_dependency
from meeting_playbook.asr.base import ASRProvider
from meeting_playbook.asr.factory import get_asr_providers_for_meeting
from meeting_playbook.asr.remote_runtime_client import AsrRuntimeUnavailableError
from meeting_playbook.audio.devices import MicDeviceNotFound, NoBlackholeDevice
from meeting_playbook.chat.repository import ChatMessageRepository
from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_session_factory_dependency,
    get_user_id_dependency,
)
from meeting_playbook.meetings.repository import (
    MeetingRepository,
    MeetingStatusConflict,
)
from meeting_playbook.playbooks.repository import PlaybookRepository
from meeting_playbook.sessions.dependencies import (
    CaptureFactory,
    Stream,
    get_capture_factory_dependency,
)
from meeting_playbook.sessions.messages import (
    AdviceChunkMessage,
    AdviceDoneMessage,
    AdvisorFailedMessage,
    ChatMessageRequestMessage,
    EndMeetingMessage,
    ErrorMessage,
    MeetingEndedMessage,
    MeetingStartedMessage,
    RequestAdviceMessage,
    StartMeetingMessage,
    parse_client_message,
)
from meeting_playbook.sessions.repository import SessionRepository
from meeting_playbook.sessions.service import SessionService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sessions"])

_CLOSE_AUTH_BYPASS = 4401
_CLOSE_NOT_FOUND = 4404
# Display value used in advisor timeout log lines. Mirrors VertexFlashAdvisor's
# _STREAM_TIMEOUT_S; kept as a separate display constant so the log line
# doesn't have to import the advisor module just to print a number.
_STREAM_TIMEOUT_S_DISPLAY = 15

# Slice-09: locale-default user_content used when the Get Advice button is
# pressed (no user_question). Persisted as the user message in chat_message
# so multi-turn history is consistent across button + chatbox paths.
_DEFAULT_PROMPT: dict[str, str] = {
    "zh-TW": "請給出戰術建議。",
    "en": "Please give tactical advice.",
}


def _classify_advisor_error(exc: BaseException) -> str:
    """Map a Vertex / google-genai exception to one of `advisor.{quota,auth,unknown}`.

    Slice-08: avoids importing google.api_core at module top so tests don't
    need GCP libs to load the router. Detection is duck-typed on the
    exception class name + message because google-genai re-raises
    `google.api_core.exceptions.{ResourceExhausted, Unauthenticated, ...}`
    and the test suite uses lightweight stand-ins of the same names.
    """
    name = type(exc).__name__
    msg = str(exc).lower()
    if name == "ResourceExhausted" or "quota" in msg or "429" in msg:
        return "advisor.quota"
    if name in {"Unauthenticated", "PermissionDenied"} or "401" in msg or "403" in msg:
        return "advisor.auth"
    return "advisor.unknown"


@router.get("/api/meetings/{meeting_id}/transcript_chunks")
async def list_transcript_chunks(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> list[dict]:
    """Historical transcript chunks for a meeting (used after session ends)."""
    meeting = await MeetingRepository(session).get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail={"error_code": "meeting.not_found", "message": "Meeting not found"},
        )
    chunks = await SessionRepository(session).list_chunks_for_meeting(meeting_id)
    return [
        {
            "id": c.id,
            "meeting_id": c.meeting_id,
            "speaker": c.speaker,
            "text": c.text,
            "started_at": c.started_at.isoformat(),
            "ended_at": c.ended_at.isoformat(),
            "asr_provider_used": c.asr_provider_used,
            "confidence": c.confidence,
        }
        for c in chunks
    ]


@router.websocket("/api/meetings/{meeting_id}/session")
async def meeting_session_endpoint(
    websocket: WebSocket,
    meeting_id: str,
    capture_factory: Annotated[CaptureFactory, Depends(get_capture_factory_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
    tactical_advisor: Annotated[TacticalAdvisor, Depends(get_tactical_advisor_dependency)],
    session_factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_session_factory_dependency)
    ],
) -> None:
    user_id = websocket.headers.get("x-user-id")
    if not user_id:
        await websocket.close(code=_CLOSE_AUTH_BYPASS, reason="auth.gateway_bypass")
        return

    meeting_repo = MeetingRepository(session)
    meeting = await meeting_repo.get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        await websocket.close(code=_CLOSE_NOT_FOUND, reason="meeting.not_found")
        return

    # Slice-11: pick ASR providers per-meeting at connect time. The pair is
    # captured into a local var so any mid-session PUT to meeting.asr_provider
    # does NOT swap the live providers (Decision 1 + spec scenario
    # "Switching meeting.asr_provider mid-session has no effect on the live WS").
    #
    # Slice-27: the `providers` dict is finalised AFTER we parse the
    # `start_meeting` frame because single mode only uses `me_provider`.
    # We resolve both providers up-front (cold-start is the same) and pick
    # the keyset later so `SessionService` sees exactly the streams the
    # capture factory returns.
    me_provider, counterparty_provider = get_asr_providers_for_meeting(meeting.asr_provider)

    await websocket.accept()

    async def _send(model_or_dict) -> None:
        if hasattr(model_or_dict, "model_dump_json"):
            await websocket.send_text(model_or_dict.model_dump_json())
        else:
            import json

            await websocket.send_text(json.dumps(model_or_dict))

    async def _send_error(code: str, message: str) -> None:
        await _send(ErrorMessage(error_code=code, message=message))

    # ─── First client message: must be start_meeting matching path id ─────
    try:
        raw = await websocket.receive_text()
        client_msg = parse_client_message(raw)
    except (ValidationError, ValueError) as exc:
        await _send_error("session.unknown_message", f"Invalid first message: {exc}")
        await websocket.close()
        return

    if not isinstance(client_msg, StartMeetingMessage):
        await _send_error("session.unknown_message", "Expected start_meeting first.")
        await websocket.close()
        return
    if client_msg.meeting_id != meeting_id:
        await _send_error(
            "session.bad_start",
            f"start_meeting id ({client_msg.meeting_id}) does not match path id ({meeting_id}).",
        )
        await websocket.close()
        return

    # ─── Pre-flight: build captures per recording mode ────────────────────
    # Slice-27: the client-provided `mode` selects the capture pipeline.
    # `dual` (default, legacy) opens BlackHole + mic; `single` opens mic
    # only and the factory MUST NOT consult `find_blackhole_device`.
    #
    # The factory raises NoBlackholeDevice / MicDeviceNotFound on failure;
    # we map both to typed error frames before any status transition or
    # WebSocket teardown. Status remains `scheduled` so the user can retry
    # after fixing their audio config.
    mode = client_msg.mode
    try:
        captures = capture_factory(meeting_id, mode)
    except NoBlackholeDevice as exc:
        await _send_error("session.no_blackhole_device", str(exc))
        await websocket.close()
        return
    except MicDeviceNotFound as exc:
        await _send_error("session.no_audio_device", str(exc))
        await websocket.close()
        return

    # Slice-27: providers mapping mirrors `captures` keyset so the
    # per-stream ASR routing invariant holds. Single mode → only `me`.
    providers: dict[Stream, ASRProvider] = {"me": me_provider}
    if "counterparty" in captures:
        providers["counterparty"] = counterparty_provider

    # ─── Transition status scheduled → in_progress ────────────────────────
    try:
        await meeting_repo.transition_status(
            meeting_id=meeting_id, expected_from="scheduled", target="in_progress"
        )
        await session.commit()
    except MeetingStatusConflict:
        await _send_error(
            "session.bad_status",
            "Meeting is not in 'scheduled' status; cannot start a new session.",
        )
        await websocket.close()
        return

    # ─── Warm up the active providers in parallel — model load is the
    # slowest cold-start step (~10–25s on first ever run); running both
    # providers via asyncio.gather keeps the wall-clock cost equivalent to
    # one. Slice-27: single mode skips the counterparty provider's warmup
    # (the dict was already trimmed above), saving ~10–25s + RAM/GPU. ───
    try:
        await asyncio.gather(*(p.warmup() for p in providers.values()))
    except AsrRuntimeUnavailableError as exc:
        # Standalone asr-runtime is down (or env var missing). Surface the
        # structured error code so the frontend can show a clear toast and
        # let the user retry once they start the runtime.
        logger.warning("asr.runtime_unavailable during warmup: %s", exc.message)
        await _send_error("asr.runtime_unavailable", exc.message)
        with contextlib.suppress(MeetingStatusConflict):
            await meeting_repo.transition_status(
                meeting_id=meeting_id,
                expected_from="in_progress",
                target="completed",
            )
            await session.commit()
        await websocket.close()
        return
    except Exception as exc:
        logger.exception("ASR warmup failed: %s", exc)
        await _send_error("session.stream_failed_at_start", f"ASR warmup failed: {exc}")
        # Roll status back so the user can retry.
        with contextlib.suppress(MeetingStatusConflict):
            await meeting_repo.transition_status(
                meeting_id=meeting_id,
                expected_from="in_progress",
                target="completed",
            )
            await session.commit()
        await websocket.close()
        return

    await _send(MeetingStartedMessage(meeting_id=meeting_id))

    session_repo = SessionRepository(session)
    service = SessionService(
        meeting_id=meeting_id,
        captures=captures,
        providers=providers,
        session_repo=session_repo,
        send=_send,
    )

    # Slice-08: at most one advice request streams at a time. A new
    # `request_advice` while one is already in-flight cancels the prior
    # task (server-side defensive — the UI also disables the button).
    advice_task: asyncio.Task[None] | None = None

    async def _run_advice(request_id: str, user_question: str | None, locale: str) -> None:
        """Open a fresh AsyncSession, gather context, stream Vertex Flash tokens.

        Slice-08 + ADR-0018: context = (last 60s of transcript chunks across
        both speakers) + (full playbook). Runs in its own session because
        the request-scoped `session` is being mutated concurrently by the
        capture / transcribe write path (SQLAlchemy AsyncSession is NOT
        safe for concurrent use).
        """
        logger.info(
            "advice request_id=%s meeting=%s locale=%s user_question=%s",
            request_id,
            meeting_id,
            locale,
            "yes" if user_question else "no",
        )
        # Slice-09: persist `user_content` derived from user_question OR the
        # locale-default prompt so button + chatbox paths produce the same
        # downstream history shape. Chatbox `content` is non-empty per spec
        # (Pydantic `min_length=1`); button path passes None.
        user_content = (
            user_question
            if user_question
            else _DEFAULT_PROMPT.get(locale, _DEFAULT_PROMPT["zh-TW"])
        )
        token_count = 0
        advisor_tokens: list[str] = []
        try:
            async with session_factory() as advice_session:
                advice_session_repo = SessionRepository(advice_session)
                playbook_repo = PlaybookRepository(advice_session)
                chat_repo = ChatMessageRepository(advice_session)
                chunks = await advice_session_repo.list_chunks_last_60s(meeting_id)
                playbook = await playbook_repo.get_or_create_for_meeting(meeting_id)
                chat_history = await chat_repo.list_for_meeting(meeting_id)
            logger.info(
                "advice request_id=%s context chunks=%d playbook=%s chat_history=%d",
                request_id,
                len(chunks),
                "present" if playbook else "missing",
                len(chat_history),
            )

            # AsyncIterator is returned from a Protocol method. Some tests
            # inject mocks whose `advise(...)` is itself an async generator
            # function; calling it returns the generator directly. Don't
            # await — iterate.
            async for token in tactical_advisor.advise(
                meeting_id=meeting_id,
                recent_chunks=chunks,
                playbook=playbook,
                me_display_name=meeting.me_display_name,
                counterparty_display_name=meeting.counterparty_display_name,
                user_question=user_question,
                locale=locale,  # type: ignore[arg-type]
                chat_history=chat_history,
            ):
                token_count += 1
                advisor_tokens.append(token)
                await _send(AdviceChunkMessage(request_id=request_id, token=token))
            logger.info("advice request_id=%s done tokens=%d", request_id, token_count)

            # Slice-09 Decision 2: persist (user, advisor) pair ONLY on
            # successful stream. Open a fresh session for the INSERT so the
            # write doesn't share connection state with the now-closed
            # context-fetch session. INSERT failure is logged but does not
            # block the user-facing `advice_done` frame.
            advisor_content = "".join(advisor_tokens)
            try:
                async with session_factory() as insert_session:
                    await ChatMessageRepository(insert_session).insert_pair_after_advice(
                        meeting_id=meeting_id,
                        user_content=user_content,
                        advisor_content=advisor_content,
                    )
            except Exception as persist_exc:
                logger.warning(
                    "advice request_id=%s persist FAILED: %s: %s",
                    request_id,
                    type(persist_exc).__name__,
                    persist_exc,
                )

            await _send(AdviceDoneMessage(request_id=request_id))
        except asyncio.CancelledError:
            # End-of-meeting / superseding request cancelled us. Re-raise
            # without sending a frame so the client doesn't see a phantom
            # error after they pressed End.
            logger.info(
                "advice request_id=%s cancelled after tokens=%d",
                request_id,
                token_count,
            )
            raise
        except TimeoutError:
            logger.warning(
                "advice request_id=%s timed out after %ss (tokens received=%d)",
                request_id,
                _STREAM_TIMEOUT_S_DISPLAY,
                token_count,
            )
            await _send(
                AdvisorFailedMessage(
                    request_id=request_id,
                    error_code="advisor.timeout",
                    message="Vertex stream timed out after 15s",
                )
            )
        except Exception as exc:
            error_code = _classify_advisor_error(exc)
            # Log the FULL traceback so Sean can debug Vertex auth / quota /
            # SDK issues from the backend log instead of staring at a generic
            # `advisor.unknown` UI message.
            logger.exception(
                "advice request_id=%s FAILED code=%s exc_type=%s tokens=%d",
                request_id,
                error_code,
                type(exc).__name__,
                token_count,
            )
            await _send(
                AdvisorFailedMessage(
                    request_id=request_id,
                    error_code=error_code,
                    message=f"{type(exc).__name__}: {exc}" if str(exc) else error_code,
                )
            )

    async def _client_listener() -> None:
        """Listen for end_meeting (or disconnect); request graceful capture stop."""
        nonlocal advice_task
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = parse_client_message(raw)
                except (ValidationError, ValueError):
                    await _send_error(
                        "session.unknown_message",
                        "Unrecognized client message during session.",
                    )
                    return
                if isinstance(msg, EndMeetingMessage):
                    return
                if isinstance(msg, RequestAdviceMessage):
                    # Slice-08 button path. Defensive: cancel any in-flight
                    # prior advice before spawning a new one. The UI disables
                    # the button, but a misbehaving / duplicated client must
                    # not pile up concurrent Vertex streams.
                    if advice_task is not None and not advice_task.done():
                        advice_task.cancel()
                        with contextlib.suppress(asyncio.CancelledError, Exception):
                            await advice_task
                    advice_task = asyncio.create_task(
                        _run_advice(msg.request_id, msg.user_question, msg.locale),
                        name=f"advice-{msg.request_id}",
                    )
                    continue
                if isinstance(msg, ChatMessageRequestMessage):
                    # Slice-09 chatbox path. Same cancel-previous policy as
                    # the button path; the user typing a new question
                    # supersedes any in-flight advice (which won't be
                    # persisted because we only INSERT on success).
                    if advice_task is not None and not advice_task.done():
                        advice_task.cancel()
                        with contextlib.suppress(asyncio.CancelledError, Exception):
                            await advice_task
                    advice_task = asyncio.create_task(
                        _run_advice(msg.request_id, msg.content, msg.locale),
                        name=f"advice-{msg.request_id}",
                    )
                    continue
        finally:
            # Gracefully stop both captures so service.run drains queued
            # chunks (including each capture's final partial buffer) before
            # the WebSocket finalizes.
            for cap in captures.values():
                with contextlib.suppress(Exception):
                    await cap.stop()

    async def _capture_runner() -> None:
        # AsyncExitStack atomically enters BOTH capture contexts. If either
        # fails to enter (e.g. RawInputStream couldn't open the device),
        # the stack closes anything that was already entered and re-raises.
        async with AsyncExitStack() as stack:
            try:
                for cap in captures.values():
                    await stack.enter_async_context(cap)
            except Exception as exc:
                logger.exception("Capture stream failed at start: %s", exc)
                with contextlib.suppress(Exception):
                    await _send_error("session.stream_failed_at_start", str(exc))
                return
            await service.run()

    listener_task = asyncio.create_task(_client_listener())
    runner_task = asyncio.create_task(_capture_runner())

    try:
        await runner_task
    except Exception as exc:
        logger.exception("capture/service runner failed: %s", exc)

    if not listener_task.done():
        listener_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await listener_task

    # Slice-08: if an advice stream is mid-flight at end-of-meeting, cancel
    # it BEFORE we send `meeting_ended` so no stray `advice_chunk` lands
    # after the WS close handshake. CancelledError is the expected path.
    if advice_task is not None and not advice_task.done():
        advice_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await advice_task

    # ─── Finalize: persist per-stream recording rows, status → completed ──
    try:
        for stream_label, cap in captures.items():
            wav_path = cap.wav_path
            if wav_path.exists():
                wav_bytes = wav_path.stat().st_size
                # Skip zero-byte WAVs — per spec, a stream that produced no
                # audio MUST NOT cause a recording row to be written.
                if wav_bytes > 0:
                    await session_repo.insert_recording(
                        meeting_id=meeting_id,
                        stream=stream_label,
                        file_path=str(wav_path),
                        bytes_size=wav_bytes,
                        # Slice-16: `AudioCaptureService.first_sample_ts`
                        # carries the wall-clock anchor; scripted test
                        # captures may not expose it — `insert_recording`
                        # falls back to `now()` when this is None.
                        started_at=getattr(cap, "first_sample_ts", None),
                    )
        # Commit so apply_speaker_attribution can read the recordings back.
        await session.commit()

        # Slice-12 (ADR-0029): run speaker attribution before transitioning
        # to `completed`. Dual-channel is a validating pass-through (zero
        # DB updates); single-channel runs diarization and rewrites chunk
        # `speaker` values. Errors surface as WS frames per spec scenario
        # "Invalid recording configuration aborts session finalize with
        # explicit error".
        # Slice-13: pass user_id + voice_enrollment_repo so single-channel
        # finalize can auto-rename the matching cluster to `me` when an
        # enrollment exists. Dual-channel path short-circuits inside
        # `apply_speaker_attribution` (the helper checks strategy type
        # before consulting the repo). Match threshold + enable flag come
        # from Settings (slice-13 task 1.2).
        from meeting_playbook.config import get_settings as _get_settings
        from meeting_playbook.speaker.diarization import (
            DiarizationProviderUnavailable,
        )
        from meeting_playbook.speaker.finalize import apply_speaker_attribution
        from meeting_playbook.speaker.strategy import InvalidSpeakerConfiguration
        from meeting_playbook.voice_enrollment.repository import (
            VoiceEnrollmentRepository,
        )

        voice_repo = VoiceEnrollmentRepository(session)
        ve_settings = _get_settings()
        voice_repo_arg = voice_repo if ve_settings.voice_enrollment_enabled else None

        try:
            await apply_speaker_attribution(
                meeting_id=meeting_id,
                repo=session_repo,
                voice_enrollment_repo=voice_repo_arg,
                current_user_id=user_id,
                match_threshold=ve_settings.voice_enrollment_match_threshold,
            )
            await session.commit()
        except (InvalidSpeakerConfiguration, DiarizationProviderUnavailable) as exc:
            logger.warning(
                "speaker_attribution_aborted",
                extra={"meeting_id": meeting_id, "error": str(exc)},
            )
            with contextlib.suppress(Exception):
                await _send_error("session.invalid_speaker_configuration", str(exc))
            # Still transition the meeting to `completed` — the recordings
            # are persisted; the user can re-run ASR / attribution later.
        with contextlib.suppress(MeetingStatusConflict):
            await meeting_repo.transition_status(
                meeting_id=meeting_id,
                expected_from="in_progress",
                target="completed",
            )
        await session.commit()
    except Exception as exc:
        logger.exception("Failed to finalize session for %s: %s", meeting_id, exc)

    with contextlib.suppress(Exception):
        await _send(MeetingEndedMessage(meeting_id=meeting_id))
        await websocket.close()

    # Slice-10: fire-and-forget spawn the post-meeting summary task. We
    # don't await — the user's UI already saw `meeting_ended` and we
    # don't want to delay the WS close handshake by 30-60s. Failures
    # surface only via GET /summary + backend log (per design.md
    # Decision 2). `spawn_summary_task` returns False when a prior
    # session's task is still in-flight; we log and move on.
    with contextlib.suppress(Exception):
        from meeting_playbook.summarization import runtime as _summary_runtime

        spawned = await _summary_runtime.spawn_summary_task(meeting_id)
        if not spawned:
            logger.info(
                "summary spawn skipped meeting=%s (already in-flight)",
                meeting_id,
            )
