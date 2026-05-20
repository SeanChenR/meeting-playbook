"""meeting-playbook ASR runtime — standalone Qwen3-ASR micro-service.

See ADR-0027 (extraction rationale) and the asr-runtime capability spec for
the wire protocol contract. This package is intentionally process-isolated
from the main FastAPI backend; do not import it from `meeting_playbook.*`.
"""

__version__ = "0.0.1"
