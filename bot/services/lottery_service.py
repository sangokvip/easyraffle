from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Iterable, Sequence

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog, Lottery, LotteryStatus, Participant, PresetWinner, Winner


async def ensure_group(session: AsyncSession, chat_id: int, title: str | None) -> None:
    from ..models import GroupConfig

    result = await session.execute(select(GroupConfig).where(GroupConfig.chat_id == chat_id))
    group = result.scalar_one_or_none()
    if group:
        if title and group.title != title:
            group.title = title
        return

    new_group = GroupConfig(chat_id=chat_id, title=title)
    session.add(new_group)


async def get_active_lottery(session: AsyncSession, chat_id: int) -> Lottery | None:
    stmt = (
        select(Lottery)
        .where(and_(Lottery.chat_id == chat_id, Lottery.status == LotteryStatus.OPEN))
        .order_by(Lottery.id.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_lottery(
    session: AsyncSession,
    *,
    chat_id: int,
    created_by: int,
    title: str,
    description: str | None,
    winners_count: int,
    join_deadline: datetime | None,
    strategy: str,
    preset_user_ids: Sequence[int] | None = None,
) -> Lottery:
    lottery = Lottery(
        chat_id=chat_id,
        created_by=created_by,
        title=title,
        description=description,
        winners_count=winners_count,
        join_deadline=join_deadline,
        status=LotteryStatus.OPEN,
        strategy=strategy,
    )
    session.add(lottery)
    await session.flush()

    if preset_user_ids:
        for user_id in preset_user_ids:
            session.add(PresetWinner(lottery_id=lottery.id, user_id=user_id))

    session.add(
        AuditLog(
            chat_id=chat_id,
            actor_id=created_by,
            action="lottery_created",
            payload=str({"lottery_id": lottery.id, "preset": preset_user_ids})
        )
    )

    return lottery


async def add_participant(
    session: AsyncSession,
    *,
    lottery: Lottery,
    user_id: int,
    username: str | None,
    first_name: str | None,
) -> Participant:
    stmt = select(Participant).where(Participant.lottery_id == lottery.id, Participant.user_id == user_id)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    participant = Participant(
        lottery_id=lottery.id,
        user_id=user_id,
        username=username,
        first_name=first_name,
    )
    session.add(participant)
    await session.flush()

    session.add(
        AuditLog(
            chat_id=lottery.chat_id,
            actor_id=user_id,
            action="joined",
            payload=str({"lottery_id": lottery.id}),
        )
    )

    return participant


async def add_participants_bulk(
    session: AsyncSession,
    *,
    lottery: Lottery,
    user_ids: Iterable[int],
) -> None:
    for uid in user_ids:
        await add_participant(session, lottery=lottery, user_id=uid, username=None, first_name=None)


async def draw_winners(
    session: AsyncSession,
    *,
    lottery: Lottery,
) -> list[Winner]:
    if lottery.status != LotteryStatus.OPEN:
        stmt = select(Winner).where(Winner.lottery_id == lottery.id)
        result = await session.execute(stmt)
        return result.scalars().all()

    now = datetime.now(timezone.utc)

    # Load participants and presets
    participants_res = await session.execute(select(Participant).where(Participant.lottery_id == lottery.id))
    participants: list[Participant] = participants_res.scalars().all()

    preset_res = await session.execute(select(PresetWinner).where(PresetWinner.lottery_id == lottery.id))
    preset_ids = [p.user_id for p in preset_res.scalars().all()]

    winners: list[Winner] = []

    # Pre-set winners first
    for user_id in preset_ids:
        target = next((p for p in participants if p.user_id == user_id), None)
        if not target:
            # auto insert placeholder participant so record consistent
            placeholder = Participant(
                lottery_id=lottery.id,
                user_id=user_id,
                username=None,
                first_name=None,
            )
            session.add(placeholder)
            participants.append(placeholder)
            target = placeholder

        winners.append(
            Winner(
                lottery_id=lottery.id,
                user_id=target.user_id,
                username=target.username,
                first_name=target.first_name,
                picked_at=now,
                preset=True,
            )
        )

    remaining_slots = max(lottery.winners_count - len(winners), 0)
    if remaining_slots > 0:
        existing_ids = {w.user_id for w in winners}
        eligible = [p for p in participants if p.user_id not in existing_ids]
        random.shuffle(eligible)
        selected = eligible[:remaining_slots]
        for participant in selected:
            winners.append(
                Winner(
                    lottery_id=lottery.id,
                    user_id=participant.user_id,
                    username=participant.username,
                    first_name=participant.first_name,
                    picked_at=now,
                    preset=False,
                )
            )

    for winner in winners:
        session.add(winner)

    await session.execute(
        update(Lottery)
        .where(Lottery.id == lottery.id)
        .values(status=LotteryStatus.COMPLETED, join_deadline=lottery.join_deadline)
    )

    session.add(
        AuditLog(
            chat_id=lottery.chat_id,
            actor_id=lottery.created_by,
            action="draw",
            payload=str({"lottery_id": lottery.id, "winner_count": len(winners)}),
        )
    )

    await session.flush()
    return winners
