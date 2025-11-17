from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from telegram import ChatMember, ChatMemberAdministrator, ChatMemberOwner, Update
from telegram.ext import ContextTypes

from .config import settings


async def is_user_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int | None = None) -> bool:
    user_id = user_id or (update.effective_user.id if update.effective_user else None)
    if user_id is None:
        return False

    if user_id in settings.global_admin_ids:
        return True

    chat = update.effective_chat
    if not chat:
        return False

    chat_member: ChatMember = await context.bot.get_chat_member(chat.id, user_id)
    return isinstance(chat_member, (ChatMemberAdministrator, ChatMemberOwner))


def format_winners(winners: Iterable) -> str:
    lines = []
    for idx, winner in enumerate(winners, start=1):
        name = winner.username or winner.first_name or str(winner.user_id)
        prefix = "[预设] " if getattr(winner, "preset", False) else ""
        lines.append(f"{idx}. {prefix}{name}")
    return "\n".join(lines)


def humanize_deadline(dt: datetime | None) -> str:
    if not dt:
        return "无"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def parse_deadline(text: str) -> datetime | None:
    text = text.strip()
    if not text:
        return None
    if text.isdigit():
        # treat as minutes from now
        minutes = int(text)
        return datetime.now(timezone.utc) + timedelta(minutes=minutes)
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None
