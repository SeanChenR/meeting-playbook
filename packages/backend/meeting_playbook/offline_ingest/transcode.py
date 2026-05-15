"""ffmpeg subprocess wrapper — normalises any supported audio container
into the project's canonical 16kHz mono 16-bit PCM WAV.

See `openspec/changes/slice-14-offline-ingest/design.md` Decision 3 for
the rationale (single subprocess covers wav / mp3 / m4a / aac / flac /
ogg without per-format Python decoders).
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


class OfflineIngestTranscodeError(RuntimeError):
    """Raised when ffmpeg exits with a non-zero return code.

    Carries the tail of ffmpeg's stderr so the pipeline can include it in
    structured logs without re-running the subprocess. Callers translate
    this into the `offline_ingest.transcode_failed` HTTP error envelope.
    """


_STDERR_TAIL_LIMIT = 4096


async def transcode_to_canonical_wav(
    *,
    staging_path: Path,
    output_path: Path,
) -> None:
    """Run ffmpeg, write `output_path` as 16kHz mono 16-bit PCM WAV.

    Per spec: on success, unlinks the staging file. On failure, removes
    both the staging file and any partial output, then raises
    `OfflineIngestTranscodeError` carrying the ffmpeg stderr tail.
    """
    if shutil.which("ffmpeg") is None:
        # Defensive — design risk 2 mitigation.
        raise OfflineIngestTranscodeError(
            "ffmpeg is not on PATH; install ffmpeg before enabling offline ingest."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",  # overwrite output_path if it exists (e.g., from a prior failed run)
            "-i",
            str(staging_path),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-sample_fmt",
            "s16",
            "-f",
            "wav",
            str(output_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr_bytes = await process.communicate()
    except FileNotFoundError as exc:
        # PATH disappeared between the which() check and the spawn.
        _cleanup(staging_path, output_path)
        raise OfflineIngestTranscodeError("ffmpeg binary disappeared during transcode.") from exc

    if process.returncode != 0:
        stderr_text = (stderr_bytes or b"").decode("utf-8", errors="replace")
        tail = stderr_text[-_STDERR_TAIL_LIMIT:].strip()
        logger.warning(
            "offline_ingest_transcode_failed",
            extra={
                "staging_path": str(staging_path),
                "returncode": process.returncode,
                "stderr_tail": tail[:500],
            },
        )
        _cleanup(staging_path, output_path)
        raise OfflineIngestTranscodeError(f"ffmpeg exited with code {process.returncode}: {tail}")

    # Success — drop the staging file; output is now the canonical WAV.
    staging_path.unlink(missing_ok=True)
    logger.info(
        "offline_ingest_transcode_succeeded",
        extra={"output_path": str(output_path)},
    )


def _cleanup(staging_path: Path, output_path: Path) -> None:
    """Best-effort cleanup of both files after a failure."""
    for candidate in (staging_path, output_path):
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            logger.warning(
                "offline_ingest_transcode_cleanup_failed",
                extra={"path": str(candidate)},
            )
