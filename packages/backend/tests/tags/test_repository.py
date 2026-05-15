"""TagRepository TDD — slice-17 task 2.2.

Five scenarios mapped from the `TagRepository enforces case-insensitive
uniqueness, cascade-on-delete, and per-meeting limit` spec requirement:

(a) case-insensitive duplicate create raises `TagNameTaken`
(b) different users 同名互不衝突 (no cross-user conflict)
(c) delete cascades junction rows via FK
(d) 11th attach raises `TagLimitExceeded(current_count=10)`
(e) duplicate attach is idempotent

Plus a few edge cases:
- name whitespace is trimmed before persistence
- empty-name create rejected with InvalidTagName
- invalid color rejected with InvalidTagColor
- detach of non-existent pair is a no-op
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from meeting_playbook.meetings.repository import MeetingRepository
from meeting_playbook.tags.models import MeetingTag, Tag
from meeting_playbook.tags.repository import (
    InvalidTagColor,
    InvalidTagName,
    TagLimitExceeded,
    TagNameTaken,
    TagRepository,
)


PALETTE_PRIMARY = "#DDD6FE"
PALETTE_SECONDARY = "#7C2D12"


async def _seed_user(engine: AsyncEngine, user_id: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES (:id, :name, :email, true)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"id": user_id, "name": user_id, "email": f"{user_id}@example.com"},
        )


@pytest.fixture
async def session_factory(migrated_engine: AsyncEngine):
    return async_sessionmaker(migrated_engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_create_rejects_case_insensitive_duplicate_name(
    migrated_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_user(migrated_engine, "u_a")
    async with session_factory() as session:
        repo = TagRepository(session)
        await repo.create(user_id="u_a", name="客戶X", color=PALETTE_PRIMARY)
        with pytest.raises(TagNameTaken):
            await repo.create(user_id="u_a", name="客戶x", color=PALETTE_PRIMARY)

    async with session_factory() as session:
        result = await session.execute(select(Tag).where(Tag.user_id == "u_a"))
        rows = list(result.scalars().all())
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_create_allows_same_name_across_different_users(
    migrated_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_user(migrated_engine, "u_a")
    await _seed_user(migrated_engine, "u_b")
    async with session_factory() as session:
        repo = TagRepository(session)
        await repo.create(user_id="u_a", name="客戶X", color=PALETTE_PRIMARY)
        await repo.create(user_id="u_b", name="客戶X", color=PALETTE_PRIMARY)

    async with session_factory() as session:
        result = await session.execute(select(Tag))
        rows = list(result.scalars().all())
        assert len(rows) == 2
        assert {r.user_id for r in rows} == {"u_a", "u_b"}


@pytest.mark.asyncio
async def test_delete_cascades_meeting_tag_rows(
    migrated_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_user(migrated_engine, "u_a")
    async with session_factory() as session:
        meeting_repo = MeetingRepository(session)
        m1 = await meeting_repo.create(
            user_id="u_a",
            title="m1",
            counterparty_display_name="cp",
            me_display_name="me",
        )
        m2 = await meeting_repo.create(
            user_id="u_a",
            title="m2",
            counterparty_display_name="cp",
            me_display_name="me",
        )
        repo = TagRepository(session)
        tag = await repo.create(user_id="u_a", name="客戶X", color=PALETTE_PRIMARY)
        await repo.attach(user_id="u_a", meeting_id=m1.id, tag_id=tag.id)
        await repo.attach(user_id="u_a", meeting_id=m2.id, tag_id=tag.id)

    async with session_factory() as session:
        repo = TagRepository(session)
        await repo.delete(user_id="u_a", tag_id=tag.id)

    async with session_factory() as session:
        result = await session.execute(select(MeetingTag).where(MeetingTag.tag_id == tag.id))
        assert list(result.scalars().all()) == []
        result = await session.execute(select(Tag).where(Tag.id == tag.id))
        assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_attach_rejects_eleventh_tag_with_current_count(
    migrated_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_user(migrated_engine, "u_a")
    async with session_factory() as session:
        meeting_repo = MeetingRepository(session)
        meeting = await meeting_repo.create(
            user_id="u_a",
            title="big",
            counterparty_display_name="cp",
            me_display_name="me",
        )
        repo = TagRepository(session)
        tag_ids: list[str] = []
        for i in range(10):
            tag = await repo.create(user_id="u_a", name=f"t{i}", color=PALETTE_PRIMARY)
            tag_ids.append(tag.id)
            await repo.attach(user_id="u_a", meeting_id=meeting.id, tag_id=tag.id)
        eleventh = await repo.create(user_id="u_a", name="t10", color=PALETTE_PRIMARY)
        with pytest.raises(TagLimitExceeded) as exc_info:
            await repo.attach(user_id="u_a", meeting_id=meeting.id, tag_id=eleventh.id)
        assert exc_info.value.current_count == 10

    async with session_factory() as session:
        result = await session.execute(
            select(MeetingTag).where(MeetingTag.meeting_id == meeting.id)
        )
        assert len(list(result.scalars().all())) == 10


@pytest.mark.asyncio
async def test_attach_duplicate_pair_is_idempotent(
    migrated_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_user(migrated_engine, "u_a")
    async with session_factory() as session:
        meeting_repo = MeetingRepository(session)
        meeting = await meeting_repo.create(
            user_id="u_a",
            title="dup",
            counterparty_display_name="cp",
            me_display_name="me",
        )
        repo = TagRepository(session)
        tag = await repo.create(user_id="u_a", name="客戶X", color=PALETTE_PRIMARY)
        first = await repo.attach(user_id="u_a", meeting_id=meeting.id, tag_id=tag.id)
        second = await repo.attach(user_id="u_a", meeting_id=meeting.id, tag_id=tag.id)

        assert first.attached_at == second.attached_at

    async with session_factory() as session:
        result = await session.execute(
            select(MeetingTag).where(MeetingTag.meeting_id == meeting.id)
        )
        assert len(list(result.scalars().all())) == 1


@pytest.mark.asyncio
async def test_create_trims_whitespace_and_rejects_empty_name(
    migrated_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_user(migrated_engine, "u_a")
    async with session_factory() as session:
        repo = TagRepository(session)
        tag = await repo.create(user_id="u_a", name="  客戶X  ", color=PALETTE_PRIMARY)
        assert tag.name == "客戶X"
        with pytest.raises(TagNameTaken):
            await repo.create(user_id="u_a", name="客戶X", color=PALETTE_SECONDARY)
        with pytest.raises(InvalidTagName):
            await repo.create(user_id="u_a", name="   ", color=PALETTE_PRIMARY)


@pytest.mark.asyncio
async def test_create_rejects_color_outside_palette(
    migrated_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_user(migrated_engine, "u_a")
    async with session_factory() as session:
        repo = TagRepository(session)
        with pytest.raises(InvalidTagColor):
            await repo.create(user_id="u_a", name="random", color="#123456")


@pytest.mark.asyncio
async def test_update_renames_and_recolors(
    migrated_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_user(migrated_engine, "u_a")
    async with session_factory() as session:
        repo = TagRepository(session)
        tag = await repo.create(user_id="u_a", name="old", color=PALETTE_PRIMARY)
        updated = await repo.update(
            user_id="u_a", tag_id=tag.id, name="new", color=PALETTE_SECONDARY
        )
        assert updated is not None
        assert updated.name == "new"
        assert updated.color == PALETTE_SECONDARY


@pytest.mark.asyncio
async def test_update_blank_name_raises_invalid_tag_name(
    migrated_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_user(migrated_engine, "u_a")
    async with session_factory() as session:
        repo = TagRepository(session)
        tag = await repo.create(user_id="u_a", name="old", color=PALETTE_PRIMARY)
        with pytest.raises(InvalidTagName):
            await repo.update(user_id="u_a", tag_id=tag.id, name="   ")


@pytest.mark.asyncio
async def test_update_invalid_color_raises(
    migrated_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_user(migrated_engine, "u_a")
    async with session_factory() as session:
        repo = TagRepository(session)
        tag = await repo.create(user_id="u_a", name="t", color=PALETTE_PRIMARY)
        with pytest.raises(InvalidTagColor):
            await repo.update(user_id="u_a", tag_id=tag.id, color="#123456")


@pytest.mark.asyncio
async def test_update_other_users_tag_returns_none(
    migrated_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_user(migrated_engine, "u_a")
    await _seed_user(migrated_engine, "u_b")
    async with session_factory() as session:
        repo = TagRepository(session)
        b_tag = await repo.create(user_id="u_b", name="other", color=PALETTE_PRIMARY)
    async with session_factory() as session:
        repo = TagRepository(session)
        result = await repo.update(user_id="u_a", tag_id=b_tag.id, name="stolen")
        assert result is None


@pytest.mark.asyncio
async def test_list_for_user_with_and_without_meeting_count(
    migrated_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_user(migrated_engine, "u_a")
    async with session_factory() as session:
        meeting_repo = MeetingRepository(session)
        m = await meeting_repo.create(
            user_id="u_a",
            title="t",
            counterparty_display_name="cp",
            me_display_name="me",
        )
        repo = TagRepository(session)
        t1 = await repo.create(user_id="u_a", name="t1", color=PALETTE_PRIMARY)
        await repo.create(user_id="u_a", name="t2", color=PALETTE_PRIMARY)
        await repo.attach(user_id="u_a", meeting_id=m.id, tag_id=t1.id)

    async with session_factory() as session:
        repo = TagRepository(session)
        plain = await repo.list_for_user(user_id="u_a")
        assert all(tag.meeting_count is None for tag in plain)
        with_count = await repo.list_for_user(user_id="u_a", with_meeting_count=True)
        counts = {tag.name: tag.meeting_count for tag in with_count}
        assert counts["t1"] == 1
        assert counts["t2"] == 0


@pytest.mark.asyncio
async def test_detach_non_existent_pair_is_noop(
    migrated_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_user(migrated_engine, "u_a")
    async with session_factory() as session:
        meeting_repo = MeetingRepository(session)
        meeting = await meeting_repo.create(
            user_id="u_a",
            title="t",
            counterparty_display_name="cp",
            me_display_name="me",
        )
        repo = TagRepository(session)
        tag = await repo.create(user_id="u_a", name="客戶X", color=PALETTE_PRIMARY)
        # Detach without prior attach — should not raise.
        await repo.detach(user_id="u_a", meeting_id=meeting.id, tag_id=tag.id)
