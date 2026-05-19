"""VoiceEnrollmentMatcher — pick the cluster whose embedding matches the
enrolled voice above a similarity threshold.

Slice 13 design decision "Matching：cosine similarity + tunable threshold":
- Cosine similarity is computed per cluster against the enrolled embedding.
- Only the single highest-similarity cluster is considered a match (a meeting
  has at most one `me`); ties never matter because there is only one row in
  `voice_enrollment` per user.
- Sub-threshold best matches return `None` so the caller leaves the chunks
  with their `speaker_cluster_<N>` labels — silently renaming a weak match
  would be worse than no rename.
"""

from __future__ import annotations

import numpy as np

# Float32 (= 4 bytes) is the storage format for embeddings written by
# `compute_enrollment_embedding` (`numpy.ndarray.tobytes()`).
_ENROLLMENT_DTYPE = np.float32


def _decode_enrolled(enrolled_embedding: bytes) -> np.ndarray:
    """Restore a 1-D float32 vector from its `numpy.tobytes()` representation.

    Length is recovered as `len(bytes) // 4`; the function does not record the
    original shape because enrollment embeddings are always 1-D (one speaker).
    """
    if not enrolled_embedding:
        raise ValueError("enrolled_embedding is empty bytes")
    if len(enrolled_embedding) % _ENROLLMENT_DTYPE().nbytes != 0:
        raise ValueError(
            "enrolled_embedding length is not a multiple of "
            f"{_ENROLLMENT_DTYPE().nbytes} (float32); cannot decode"
        )
    return np.frombuffer(enrolled_embedding, dtype=_ENROLLMENT_DTYPE)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity in `[-1.0, 1.0]`.

    Returns `0.0` when either input is the zero vector — the caller treats a
    zero similarity as "no match", which is the safe default for any
    degenerate input pyannote might emit (e.g. silent chunk).
    """
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class VoiceEnrollmentMatcher:
    """Stateless matcher (per-call only); keep as a class so future
    threshold-tuning or model-swapping has a stable seam.
    """

    def find_me_cluster(
        self,
        enrolled_embedding: bytes,
        cluster_embeddings: dict[int, np.ndarray],
        threshold: float = 0.5,
    ) -> int | None:
        """Return the cluster_id whose embedding has the highest cosine
        similarity to `enrolled_embedding`, provided that similarity is
        `>= threshold`. Return `None` otherwise (no match / empty input).

        Inputs are not mutated. The `cluster_embeddings` dict is iterated
        in stable insertion order; the returned cluster id is whatever key
        wins the max — ties are not currently expected because enrollment
        is a single-speaker problem.
        """
        if not cluster_embeddings:
            return None

        enrolled = _decode_enrolled(enrolled_embedding)

        best_id: int | None = None
        best_score: float = -1.0
        for cluster_id, cluster_emb in cluster_embeddings.items():
            score = _cosine(enrolled, cluster_emb)
            if score > best_score:
                best_score = score
                best_id = cluster_id

        if best_id is None or best_score < threshold:
            return None
        return best_id
