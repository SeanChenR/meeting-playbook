"""Relax `transcript_chunk.speaker` CHECK to allow `speaker_cluster_*` values.

Revision ID: 0010_relax_transcript_chunk_speaker_check
Revises: 0009_create_voice_enrollment
Create Date: 2026-05-15

Slice-12 / ADR-0029 widened the `speaker` value space from
`{me, counterparty, system}` to also include `speaker_cluster_<N>` /
`speaker_cluster_unknown` for Single-channel mode. The original CHECK
constraint installed by `0003_create_session_tables` rejects those new
values; this migration drops it and installs a relaxed one that accepts
both the binary labels AND the cluster labels via regex.

`system` is preserved for historical rows / future internal uses (no slice
emits it today but it was in the original constraint).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0010_relax_chunk_speaker_check"
down_revision: str | None = "0009_create_voice_enrollment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_OLD_CHECK = "speaker IN ('me', 'counterparty', 'system')"
_NEW_CHECK = (
    "speaker IN ('me', 'counterparty', 'system') OR speaker ~ '^speaker_cluster_(\\d+|unknown)$'"
)


def upgrade() -> None:
    op.drop_constraint("transcript_chunk_speaker_check", "transcript_chunk", type_="check")
    op.create_check_constraint(
        "transcript_chunk_speaker_check",
        "transcript_chunk",
        _NEW_CHECK,
    )


def downgrade() -> None:
    op.drop_constraint("transcript_chunk_speaker_check", "transcript_chunk", type_="check")
    # Defensive: any pre-existing `speaker_cluster_*` rows would violate the
    # restored strict CHECK. Rather than let the migration fail mid-run, we
    # downgrade those values to `system` (a pre-slice-12 catch-all the original
    # constraint already accepts). Down-rollback is rare; this is the
    # least-surprising lossy fix.
    op.execute(
        "UPDATE transcript_chunk SET speaker = 'system' "
        "WHERE speaker NOT IN ('me', 'counterparty', 'system')"
    )
    op.create_check_constraint(
        "transcript_chunk_speaker_check",
        "transcript_chunk",
        _OLD_CHECK,
    )
