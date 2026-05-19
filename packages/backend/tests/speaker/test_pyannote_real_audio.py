"""Real-audio acceptance test for `PyannoteProvider.diarize`.

Covers Task 2.4 of slice-12: load the multi-speaker fixture WAV
(`tests/speaker/fixtures/multi_speakers_zh.wav`), feed it to the real
pyannote pipeline, and verify the spec contract:

(a) at least 2 distinct cluster ids are returned;
(b) segments are sorted by start_ms and non-overlapping
    (the `DiarizationProvider` protocol guarantee);
(c) wall-clock latency is captured and appended to
    `tests/speaker/fixtures/compare_diarization.md` so ADR-0029 can
    cite a real measurement.

Skipped unless `PYANNOTE_AUTH_TOKEN` is set in the environment AND the
fixture file exists. The first invocation downloads the model from
HuggingFace and can take ~1–2 minutes; subsequent runs use the local
HF cache (~5–15s on M-series).
"""

from __future__ import annotations

import os
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from meeting_playbook.speaker.diarization import DiarizationSegment
from meeting_playbook.speaker.pyannote_provider import PyannoteProvider

_FIXTURE = Path(__file__).parent / "fixtures" / "multi_speakers_zh.wav"
_LATENCY_REPORT = Path(__file__).parent / "fixtures" / "compare_diarization.md"


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("PYANNOTE_AUTH_TOKEN"),
        reason="PYANNOTE_AUTH_TOKEN not set; real-audio diarization skipped",
    ),
    pytest.mark.skipif(
        not _FIXTURE.exists(),
        reason=f"fixture not present at {_FIXTURE}",
    ),
]


@pytest.fixture(scope="module")
def provider() -> PyannoteProvider:
    token = os.environ["PYANNOTE_AUTH_TOKEN"]
    return PyannoteProvider(token=token)


def test_diarize_returns_at_least_two_clusters(provider: PyannoteProvider) -> None:
    segments = provider.diarize(_FIXTURE)
    cluster_ids = {s.cluster_id for s in segments}
    assert len(cluster_ids) >= 2, (
        f"expected ≥2 distinct cluster_ids from multi-speaker fixture, got {sorted(cluster_ids)}"
    )


def test_segments_sorted_and_non_overlapping(provider: PyannoteProvider) -> None:
    segments = provider.diarize(_FIXTURE)
    assert segments, "diarize returned no segments"
    for i, seg in enumerate(segments):
        assert isinstance(seg, DiarizationSegment)
        assert seg.start_ms < seg.end_ms, f"segment {i} has start ≥ end: {seg}"
    last_end = -1
    for i, seg in enumerate(segments):
        assert seg.start_ms >= last_end, (
            f"segment {i} starts at {seg.start_ms}ms but previous ended at "
            f"{last_end}ms (overlap / out-of-order)"
        )
        last_end = seg.end_ms


def test_latency_recorded_for_adr(provider: PyannoteProvider) -> None:
    """Run diarize three times, capture p50 / p95, append to the comparison doc.

    Three runs is the smallest sample that lets us report a non-trivial p95;
    the pipeline is already loaded (provider is module-scoped), so each call
    measures the inference cost alone, not the one-time model load.
    """
    runs = 3
    durations_s: list[float] = []
    cluster_counts: list[int] = []
    for _ in range(runs):
        start = time.perf_counter()
        segments = provider.diarize(_FIXTURE)
        durations_s.append(time.perf_counter() - start)
        cluster_counts.append(len({s.cluster_id for s in segments}))

    durations_s.sort()
    p50 = statistics.median(durations_s)
    # statistics.quantiles needs n>=2; with runs=3 we compute p95 by index.
    p95 = durations_s[-1]

    fixture_duration_s = _wav_duration_seconds(_FIXTURE)
    realtime_ratio_p95 = p95 / fixture_duration_s if fixture_duration_s else float("nan")

    report = _LATENCY_REPORT
    report.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    entry = (
        f"\n## {timestamp} — multi_speakers_zh.wav ({fixture_duration_s:.1f}s)\n\n"
        f"- runs: {runs}\n"
        f"- p50 latency: {p50:.2f}s\n"
        f"- p95 latency: {p95:.2f}s\n"
        f"- p95 realtime ratio: {realtime_ratio_p95:.2f}x "
        f"(diarize_seconds / audio_seconds; < 1.0 = faster than realtime)\n"
        f"- cluster counts per run: {cluster_counts}\n"
    )
    if not report.exists():
        report.write_text(
            "# Diarization latency comparison\n\n"
            "Appended by `tests/speaker/test_pyannote_real_audio.py`. "
            "ADR-0029 cites the most recent entry for the v1.1 baseline.\n",
            encoding="utf-8",
        )
    with report.open("a", encoding="utf-8") as fh:
        fh.write(entry)

    assert p95 > 0


def _wav_duration_seconds(wav_path: Path) -> float:
    import wave

    with wave.open(str(wav_path), "rb") as wav:
        frames = wav.getnframes()
        rate = wav.getframerate()
    if rate <= 0:
        return 0.0
    return frames / rate
