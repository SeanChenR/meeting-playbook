"""PlaybookRepository contract.

Per spec (slice-04-playbook-editor, playbook-management):
- Each meeting has at most one playbook (the repo's `get_or_create_for_meeting`
  enforces this — first call inserts, second call returns the same id)
- PUT performs a full upsert with seven content fields, advancing updated_at
- Content fields accept arbitrary markdown (separate test below)
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.playbooks.repository import PlaybookRepository, PlaybookUpsertPayload


async def _seed_user_and_meeting(session: AsyncSession, *, meeting_id: str) -> None:
    """Insert a user + meeting that the playbook FK can satisfy."""
    user_id = f"u_{meeting_id}"
    await session.execute(
        text(
            """
            INSERT INTO "user" (id, name, email, "emailVerified")
            VALUES (:uid, :name, :email, true)
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"uid": user_id, "name": user_id, "email": f"{user_id}@example.com"},
    )
    await session.execute(
        text(
            """
            INSERT INTO meeting (id, user_id, title, counterparty_display_name, me_display_name)
            VALUES (:mid, :uid, 'T', 'C', 'M')
            """
        ),
        {"mid": meeting_id, "uid": user_id},
    )
    await session.commit()


@pytest.mark.asyncio
async def test_get_or_create_first_call_inserts_empty_playbook(db_session: AsyncSession):
    """First read auto-creates a row with all seven content fields = ''."""
    await _seed_user_and_meeting(db_session, meeting_id="m_first_get")

    repo = PlaybookRepository(db_session)
    playbook = await repo.get_or_create_for_meeting("m_first_get")

    assert playbook.meeting_id == "m_first_get"
    assert playbook.id.startswith("pb_")
    assert playbook.free_form_markdown == ""
    assert playbook.objective == ""
    assert playbook.counterparty_profile == ""
    assert playbook.anticipated_topics == ""
    assert playbook.anticipated_objections == ""
    assert playbook.talking_points == ""
    assert playbook.red_lines == ""


@pytest.mark.asyncio
async def test_get_or_create_returns_same_id_on_second_call(db_session: AsyncSession):
    """Second call returns the row created by the first call, not a new id."""
    await _seed_user_and_meeting(db_session, meeting_id="m_second_get")

    repo = PlaybookRepository(db_session)
    first = await repo.get_or_create_for_meeting("m_second_get")
    second = await repo.get_or_create_for_meeting("m_second_get")

    assert first.id == second.id


@pytest.mark.asyncio
async def test_upsert_full_payload_replaces_all_seven_fields(db_session: AsyncSession):
    """upsert_for_meeting replaces every content field; updated_at advances."""
    await _seed_user_and_meeting(db_session, meeting_id="m_upsert")
    repo = PlaybookRepository(db_session)
    initial = await repo.get_or_create_for_meeting("m_upsert")
    initial_updated_at = initial.updated_at

    # Force a noticeable timestamp gap on systems with low clock resolution.
    await asyncio.sleep(0.01)

    payload: PlaybookUpsertPayload = {
        "free_form_markdown": "# Brief",
        "objective": "Close Q3 deal",
        "counterparty_profile": "林經理",
        "anticipated_topics": "pricing",
        "anticipated_objections": "budget",
        "talking_points": "value prop",
        "red_lines": "no discount below 30%",
    }
    saved = await repo.upsert_for_meeting("m_upsert", payload)

    assert saved.id == initial.id
    assert saved.free_form_markdown == "# Brief"
    assert saved.objective == "Close Q3 deal"
    assert saved.counterparty_profile == "林經理"
    assert saved.anticipated_topics == "pricing"
    assert saved.anticipated_objections == "budget"
    assert saved.talking_points == "value prop"
    assert saved.red_lines == "no discount below 30%"
    assert saved.updated_at > initial_updated_at


@pytest.mark.asyncio
async def test_upsert_creates_row_when_none_exists(db_session: AsyncSession):
    """upsert_for_meeting must work even if no playbook row exists yet."""
    await _seed_user_and_meeting(db_session, meeting_id="m_upsert_fresh")
    repo = PlaybookRepository(db_session)

    saved = await repo.upsert_for_meeting(
        "m_upsert_fresh",
        {
            "free_form_markdown": "fresh",
            "objective": "",
            "counterparty_profile": "",
            "anticipated_topics": "",
            "anticipated_objections": "",
            "talking_points": "",
            "red_lines": "",
        },
    )
    assert saved.free_form_markdown == "fresh"


@pytest.mark.asyncio
async def test_upsert_with_chinese_english_mixed_markdown(db_session: AsyncSession):
    """Spec Requirement: content fields accept arbitrary markdown including
    Chinese-English mix; round-trip is byte-for-byte (no encoding mangling)."""
    await _seed_user_and_meeting(db_session, meeting_id="m_markdown")
    repo = PlaybookRepository(db_session)

    body_lines = [
        "# 季度績效檢討 — Q3 Review",
        "",
        "## 目標 Objectives",
        "",
        "- 完成 **Acme Corp** 的合約簽訂 (預計 $250k ARR)",
        "- 把對方的擔憂從 *price* 拉回 *value*",
        "",
        "## 關鍵字 Keywords",
        "",
        "1. ROI 投資報酬率",
        "2. SLA 服務水準",
        "3. 整合期程 — integration timeline",
        "",
        "```python",
        "def discount(price: float, pct: float) -> float:",
        "    return price * (1 - pct)",
        "```",
        "",
        "> 注意：對方主管 林經理 有 final say 🚦",
    ]
    while len(body_lines) < 60:
        body_lines.append(f"- 細節 line {len(body_lines)}: 中英 mixed content")
    body = "\n".join(body_lines)

    payload: PlaybookUpsertPayload = {
        "free_form_markdown": body,
        "objective": "簽下 Acme Corp Q3 contract",
        "counterparty_profile": "林經理 — Director of Procurement",
        "anticipated_topics": "- pricing\n- timeline\n- SLA 條款",
        "anticipated_objections": "**budget freeze 🥶** + competitor X 的報價",
        "talking_points": "1. ROI calculation\n2. case study at 客戶 Y",
        "red_lines": "不得低於 30% 折扣 / no NDA exception",
    }
    saved = await repo.upsert_for_meeting("m_markdown", payload)

    assert saved.free_form_markdown == body
    assert saved.objective == payload["objective"]
    assert saved.counterparty_profile == payload["counterparty_profile"]
    assert saved.anticipated_topics == payload["anticipated_topics"]
    assert saved.anticipated_objections == payload["anticipated_objections"]
    assert saved.talking_points == payload["talking_points"]
    assert saved.red_lines == payload["red_lines"]
