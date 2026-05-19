"""Smoke test for PyannoteProvider — runs the full pyannote.audio pipeline
on a WAV file and prints the resulting speaker segments.

Usage:
    cd packages/backend
    uv run python scripts/test_pyannote.py <path_to.wav>

First run downloads `pyannote/speaker-diarization-3.1` (~300MB) and the
`pyannote/segmentation-3.0` dependency from HuggingFace Hub. Subsequent
runs reuse the cache under `~/.cache/huggingface/`.

Requirements:
- `PYANNOTE_AUTH_TOKEN` in `.env` (HF read token)
- Accepted gating terms at:
    https://huggingface.co/pyannote/speaker-diarization-3.1
    https://huggingface.co/pyannote/segmentation-3.0
- A 16kHz mono WAV input (use `ffmpeg -i in.mp4 -ar 16000 -ac 1 out.wav` to convert)

What this verifies end-to-end:
1. HF token is valid + gating accepted (else 401/403)
2. PyannoteProvider lazy-loads the pipeline correctly
3. _annotation_to_segments enforces the DiarizationProvider contract
4. The returned cluster_ids look sensible for the input
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Make `meeting_playbook` importable when running this script directly via
# `uv run python scripts/test_pyannote.py …` from `packages/backend/`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from meeting_playbook.config import get_settings
from meeting_playbook.speaker.diarization import DiarizationProviderUnavailable
from meeting_playbook.speaker.pyannote_provider import PyannoteProvider


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2

    wav_path = Path(sys.argv[1]).expanduser().resolve()
    if not wav_path.exists():
        print(f"❌ File not found: {wav_path}")
        return 1

    settings = get_settings()
    token = settings.pyannote_auth_token
    if not token:
        print("❌ PYANNOTE_AUTH_TOKEN is empty in your .env")
        return 1

    print("▶ Loading pyannote pipeline (first time may download ~300MB)…")
    t0 = time.monotonic()
    try:
        provider = PyannoteProvider(token=token)
        segments = provider.diarize(wav_path)
    except DiarizationProviderUnavailable as exc:
        print(f"❌ Provider unavailable: {exc}")
        print(
            "   Hint: confirm you accepted gating at "
            "huggingface.co/pyannote/speaker-diarization-3.1 + segmentation-3.0"
        )
        return 1
    except Exception as exc:
        print(f"❌ Diarization failed: {type(exc).__name__}: {exc}")
        return 1
    elapsed = time.monotonic() - t0

    if not segments:
        print(f"⚠ No segments returned (silent file?). Took {elapsed:.1f}s.")
        return 1

    cluster_ids = sorted({s.cluster_id for s in segments})
    duration_ms = segments[-1].end_ms - segments[0].start_ms

    print()
    print(f"✓ Pipeline ran in {elapsed:.1f}s")
    print(f"✓ {len(segments)} segments spanning {duration_ms / 1000:.1f}s")
    print(f"✓ Detected {len(cluster_ids)} distinct speaker(s): {cluster_ids}")
    print()
    print("First 10 segments:")
    print(f"  {'start (s)':>10}  {'end (s)':>10}  {'cluster':>8}")
    for seg in segments[:10]:
        print(
            f"  {seg.start_ms / 1000:>10.2f}  {seg.end_ms / 1000:>10.2f}  "
            f"speaker_cluster_{seg.cluster_id:<3}"
        )
    if len(segments) > 10:
        print(f"  …({len(segments) - 10} more)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
