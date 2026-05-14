"""compute_enrollment_embedding — extract a single-speaker voice embedding
from a 30-second enrollment WAV using the project's pyannote pipeline.

Slice-13 design decision "Embedding 來源：重用 pyannote DiarizeOutput.speaker_embeddings":
we deliberately do NOT add a second model dependency for speaker embedding —
the diarization pipeline already produces per-speaker x-vectors as a by-product.
Feeding the enrollment WAV through the same pipeline keeps the embedding
space identical to what's used at session-finalize matching time.

Validation:
- Exactly one speaker detected (multi-speaker samples are user error — the
  user probably had background voice / TV / a colleague in the room).
- The embedding vector is non-zero (silent / dropped sample defense).
- The pipeline is available (PYANNOTE_AUTH_TOKEN configured).

All failures raise `InvalidEnrollmentSample` with a message naming the
specific cause so the API layer can surface it back to the user.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from meeting_playbook.config import get_settings
from meeting_playbook.speaker.diarization import DiarizationProviderUnavailable
from meeting_playbook.speaker.pyannote_provider import PyannoteProvider


class InvalidEnrollmentSample(ValueError):
    """Raised when a candidate enrollment WAV cannot produce a usable
    single-speaker embedding (multi-speaker, silent, or the pipeline is
    unavailable). The API layer translates this to HTTP 422
    `voice_enrollment.invalid_sample` with the message body.
    """


def compute_enrollment_embedding(
    wav_path: Path, *, provider: PyannoteProvider | None = None
) -> bytes:
    """Run the pyannote pipeline on `wav_path` and return the user's voice
    embedding as float32 bytes (via `numpy.ndarray.tobytes()`).

    `provider` is injectable so tests can use a stub; production callers
    omit it and inherit the module-level default (PyannoteProvider gated
    on PYANNOTE_AUTH_TOKEN).

    Raises `InvalidEnrollmentSample` per the spec scenarios.
    """
    if provider is None:
        settings = get_settings()
        if not settings.pyannote_auth_token:
            raise InvalidEnrollmentSample(
                "PYANNOTE_AUTH_TOKEN is not configured; cannot enroll voice. See README §3.5."
            )
        try:
            provider = PyannoteProvider(token=settings.pyannote_auth_token)
        except DiarizationProviderUnavailable as exc:
            raise InvalidEnrollmentSample(str(exc)) from exc

    try:
        segments = provider.diarize(wav_path)
    except DiarizationProviderUnavailable as exc:
        raise InvalidEnrollmentSample(str(exc)) from exc

    cluster_ids = {seg.cluster_id for seg in segments}
    if not cluster_ids:
        raise InvalidEnrollmentSample(
            "Pipeline detected no speech in the sample; please record again "
            "with a non-silent 30-second clip."
        )
    if len(cluster_ids) > 1:
        raise InvalidEnrollmentSample(
            f"Pipeline detected {len(cluster_ids)} speakers in the sample; "
            "enrollment requires exactly 1 speaker. Re-record in a quieter "
            "environment with no background voices."
        )

    embeddings = provider.cluster_embeddings()
    if not embeddings:
        raise InvalidEnrollmentSample(
            "Pipeline did not produce speaker embeddings; the model output "
            "is incompatible with this version of voice enrollment."
        )

    cluster_id = next(iter(cluster_ids))
    if cluster_id not in embeddings:
        raise InvalidEnrollmentSample(
            f"Speaker cluster {cluster_id} has no matching embedding row; "
            "pipeline output is inconsistent."
        )

    embedding = np.asarray(embeddings[cluster_id], dtype=np.float32)
    if float(np.linalg.norm(embedding)) == 0.0:
        raise InvalidEnrollmentSample(
            "Speaker embedding is the zero vector — sample is likely silent "
            "or below the noise floor. Please re-record."
        )

    return embedding.tobytes()
