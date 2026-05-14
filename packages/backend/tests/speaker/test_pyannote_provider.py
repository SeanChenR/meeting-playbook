"""Tests for `PyannoteProvider`.

Verifies the two spec scenarios under "PyannoteProvider implements
DiarizationProvider via HuggingFace pretrained model":
- First diarize call loads pipeline; subsequent calls reuse it.
- Missing token raises `DiarizationProviderUnavailable`.

Also verifies the runtime-checkable `DiarizationProvider` Protocol is
satisfied, and that pyannote `Annotation` → `list[DiarizationSegment]`
conversion preserves the protocol contract (sorted, non-overlapping,
1-based cluster_id).

The real model is never loaded — `loader` is dependency-injected with a
stub so these tests run in milliseconds and require no network / token.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from meeting_playbook.speaker.diarization import (
    DiarizationProvider,
    DiarizationProviderUnavailable,
)
from meeting_playbook.speaker.pyannote_provider import (
    PyannoteProvider,
    _annotation_to_segments,
)


# ───── Fake pyannote Annotation / Segment ──────────────────────────────


class _FakeSegment:
    """Minimal stand-in for `pyannote.core.Segment`."""

    def __init__(self, start: float, end: float) -> None:
        self.start = start
        self.end = end


class _FakeAnnotation:
    """Minimal stand-in for `pyannote.core.Annotation`. Mirrors the
    `.itertracks(yield_label=True)` shape we depend on.
    """

    def __init__(self, tracks: list[tuple[_FakeSegment, str, str]]) -> None:
        self._tracks = tracks

    def itertracks(self, yield_label: bool = False):
        for track in self._tracks:
            if yield_label:
                yield track
            else:
                yield track[:2]


class _FakePipeline:
    """Stand-in for `pyannote.audio.Pipeline` — records calls."""

    def __init__(self, annotation: _FakeAnnotation) -> None:
        self._annotation = annotation
        self.calls: list[str] = []

    def __call__(self, wav_path: str) -> _FakeAnnotation:
        self.calls.append(wav_path)
        return self._annotation


# ───── Tests ──────────────────────────────────────────────────────────


def test_provider_satisfies_diarization_protocol() -> None:
    provider = PyannoteProvider(
        token="dummy", loader=lambda c, t: _FakePipeline(_FakeAnnotation([]))
    )
    assert isinstance(provider, DiarizationProvider)


def test_first_diarize_loads_pipeline_subsequent_calls_reuse() -> None:
    pipeline = _FakePipeline(
        _FakeAnnotation(
            [
                (_FakeSegment(0.0, 1.0), "_", "SPEAKER_00"),
                (_FakeSegment(1.0, 2.0), "_", "SPEAKER_01"),
            ]
        )
    )
    load_calls: list[tuple[str, str]] = []

    def fake_loader(checkpoint: str, token: str):
        load_calls.append((checkpoint, token))
        return pipeline

    provider = PyannoteProvider(token="tok_abc", loader=fake_loader)

    first = provider.diarize(Path("/tmp/a.wav"))
    second = provider.diarize(Path("/tmp/b.wav"))

    assert len(load_calls) == 1, "pipeline loaded exactly once across two diarize calls"
    assert load_calls[0] == ("pyannote/speaker-diarization-3.1", "tok_abc")
    assert pipeline.calls == ["/tmp/a.wav", "/tmp/b.wav"]
    assert len(first) == 2 and len(second) == 2


def test_empty_token_raises_diarization_provider_unavailable() -> None:
    with pytest.raises(DiarizationProviderUnavailable) as excinfo:
        PyannoteProvider(token="", loader=lambda c, t: _FakePipeline(_FakeAnnotation([])))

    assert "PYANNOTE_AUTH_TOKEN" in str(excinfo.value)


def test_loader_returning_none_raises_diarization_provider_unavailable() -> None:
    """When pyannote 4.x sees a bad checkpoint / unauthorized download it can
    return `None` rather than raising — we must surface that as unavailable.
    """

    # Wrap real loader path: simulate by using the actual default loader with
    # a faked Pipeline.from_pretrained behaviour through monkey-injection.
    def fake_loader(checkpoint: str, token: str):
        return None  # mimic pyannote returning None on auth failure

    # Reuse the default loader's `None` guard by constructing provider with
    # a custom loader that re-routes to the default's None-handling logic.
    from meeting_playbook.speaker.pyannote_provider import _default_pipeline_loader

    # Patch Pipeline import at runtime so default loader sees a stubbed
    # `Pipeline.from_pretrained` returning None.
    class _StubPipelineClass:
        @staticmethod
        def from_pretrained(checkpoint: str, token: str):
            return None

    import sys
    import types

    fake_module = types.ModuleType("pyannote.audio")
    fake_module.Pipeline = _StubPipelineClass  # type: ignore[attr-defined]
    sys.modules["pyannote.audio"] = fake_module
    try:
        with pytest.raises(DiarizationProviderUnavailable) as excinfo:
            _default_pipeline_loader("pyannote/speaker-diarization-3.1", "tok")
        assert "gating" in str(excinfo.value).lower() or "none" in str(excinfo.value).lower()
    finally:
        # Real pyannote.audio is no longer needed for the rest of the test session
        sys.modules.pop("pyannote.audio", None)
    # Sanity-check fake_loader was not invoked (test scaffolding for clarity)
    assert fake_loader is not _default_pipeline_loader


# ───── _annotation_to_segments unit tests ─────────────────────────────


def test_annotation_to_segments_maps_speaker_labels_to_1based_cluster_ids() -> None:
    annotation = _FakeAnnotation(
        [
            (_FakeSegment(0.0, 1.0), "_", "SPEAKER_00"),
            (_FakeSegment(1.0, 2.0), "_", "SPEAKER_01"),
            (_FakeSegment(2.0, 3.0), "_", "SPEAKER_00"),
        ]
    )

    segments = _annotation_to_segments(annotation)

    assert [s.start_ms for s in segments] == [0, 1000, 2000]
    assert [s.end_ms for s in segments] == [1000, 2000, 3000]
    assert [s.cluster_id for s in segments] == [1, 2, 1]


def test_annotation_to_segments_clips_overlap_to_protocol_contract() -> None:
    """pyannote may emit overlapping segments (cross-talk). The provider
    enforces the non-overlap rule by clipping the later segment's start.
    """
    annotation = _FakeAnnotation(
        [
            (_FakeSegment(0.0, 2.0), "_", "SPEAKER_00"),
            (_FakeSegment(1.5, 3.0), "_", "SPEAKER_01"),  # overlaps first by 500ms
        ]
    )

    segments = _annotation_to_segments(annotation)

    assert segments[0].end_ms <= segments[1].start_ms
    assert segments[0].start_ms < segments[0].end_ms
    assert segments[1].start_ms < segments[1].end_ms


def test_annotation_to_segments_drops_zero_length_input_segments() -> None:
    annotation = _FakeAnnotation(
        [
            (_FakeSegment(0.0, 1.0), "_", "SPEAKER_00"),
            (_FakeSegment(1.0, 1.0), "_", "SPEAKER_01"),  # zero-length
            (_FakeSegment(2.0, 3.0), "_", "SPEAKER_00"),
        ]
    )

    segments = _annotation_to_segments(annotation)

    assert len(segments) == 2
    assert [s.start_ms for s in segments] == [0, 2000]


def test_annotation_to_segments_sorts_unordered_input() -> None:
    annotation = _FakeAnnotation(
        [
            (_FakeSegment(2.0, 3.0), "_", "SPEAKER_01"),
            (_FakeSegment(0.0, 1.0), "_", "SPEAKER_00"),
        ]
    )

    segments = _annotation_to_segments(annotation)

    assert [s.start_ms for s in segments] == [0, 2000]
    # First-seen order in the sorted sequence determines cluster_id.
    assert segments[0].cluster_id == 1
    assert segments[1].cluster_id == 2
