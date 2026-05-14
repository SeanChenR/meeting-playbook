"""Tests for `VoiceEnrollmentMatcher.find_me_cluster`.

Verifies the three spec scenarios under "VoiceEnrollmentMatcher picks the
highest-similarity cluster above threshold":
- highest similarity above threshold is returned
- all similarities below threshold returns None
- empty cluster set returns None
"""

from __future__ import annotations

import numpy as np

from meeting_playbook.voice_enrollment.matcher import VoiceEnrollmentMatcher


def _bytes(vec: list[float]) -> bytes:
    """Encode a Python float list as a float32 bytes blob (matches storage)."""
    return np.asarray(vec, dtype=np.float32).tobytes()


def _vec(values: list[float]) -> np.ndarray:
    return np.asarray(values, dtype=np.float32)


def test_highest_similarity_above_threshold_is_returned() -> None:
    """Cluster 2's embedding is identical to the enrolled vector → similarity
    = 1.0; cluster 1 / 3 are orthogonal-ish → low similarity. Cluster 2 wins.
    """
    enrolled = _bytes([1.0, 0.0, 0.0])
    clusters = {
        1: _vec([0.0, 1.0, 0.0]),  # orthogonal → similarity 0
        2: _vec([1.0, 0.0, 0.0]),  # identical → similarity 1
        3: _vec([0.5, 0.5, 0.0]),  # ~0.707 similarity
    }

    matcher = VoiceEnrollmentMatcher()
    result = matcher.find_me_cluster(enrolled, clusters, threshold=0.5)

    assert result == 2


def test_all_similarities_below_threshold_returns_none() -> None:
    """All clusters score below the 0.9 threshold → no match."""
    enrolled = _bytes([1.0, 0.0, 0.0])
    clusters = {
        1: _vec([0.5, 0.5, 0.0]),  # ~0.707
        2: _vec([0.0, 1.0, 0.0]),  # 0.0
    }

    matcher = VoiceEnrollmentMatcher()
    result = matcher.find_me_cluster(enrolled, clusters, threshold=0.9)

    assert result is None


def test_empty_cluster_set_returns_none() -> None:
    enrolled = _bytes([1.0, 0.0, 0.0])
    matcher = VoiceEnrollmentMatcher()

    result = matcher.find_me_cluster(enrolled, {}, threshold=0.5)

    assert result is None


def test_inputs_are_not_mutated() -> None:
    """The matcher copies what it needs; the caller's dict and arrays remain
    untouched after the call.
    """
    enrolled = _bytes([1.0, 0.0, 0.0])
    original_cluster_1 = _vec([1.0, 0.0, 0.0])
    cluster_1_snapshot = original_cluster_1.copy()
    clusters: dict[int, np.ndarray] = {1: original_cluster_1}
    clusters_snapshot = dict(clusters)

    VoiceEnrollmentMatcher().find_me_cluster(enrolled, clusters, threshold=0.5)

    assert np.array_equal(original_cluster_1, cluster_1_snapshot)
    assert clusters == clusters_snapshot


def test_zero_vector_cluster_yields_no_match() -> None:
    """Pyannote can emit zero embeddings on silent / pathological audio.
    Cosine similarity for a zero vector is `0.0` (per _cosine), which falls
    below the typical threshold of 0.5 and returns None.
    """
    enrolled = _bytes([1.0, 0.0, 0.0])
    clusters = {1: _vec([0.0, 0.0, 0.0])}

    result = VoiceEnrollmentMatcher().find_me_cluster(enrolled, clusters, threshold=0.5)

    assert result is None


def test_threshold_inclusive_at_exact_match() -> None:
    """Similarity equal to the threshold passes (>= comparison)."""
    enrolled = _bytes([1.0, 0.0, 0.0])
    # Construct cluster vector whose cosine similarity to enrolled is exactly 0.5
    clusters = {1: _vec([0.5, np.sqrt(3) / 2, 0.0])}  # 60-degree rotation

    result = VoiceEnrollmentMatcher().find_me_cluster(enrolled, clusters, threshold=0.5)

    assert result == 1
