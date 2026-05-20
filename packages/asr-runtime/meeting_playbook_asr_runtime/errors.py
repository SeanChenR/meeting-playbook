"""Runtime errors emitted by the ASR routes.

`RuntimeUnavailableError` is the single failure type the routes raise when
the underlying model can't service a request — invalid audio payload,
model crash, MPS OOM, etc. The exception handler in `server.py` translates
it into the `{"error_code": "asr.runtime_unavailable", ...}` envelope
defined in `schemas.py`.
"""

from __future__ import annotations


class RuntimeUnavailableError(Exception):
    """Raised when transcription cannot proceed. Mapped to HTTP 503 +
    `error_code: asr.runtime_unavailable`."""

    def __init__(self, message: str, *, retriable: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.retriable = retriable
