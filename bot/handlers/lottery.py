from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from telegram import Update
from telegram.ext import (
    Application,
    CallbackContext,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from sqlalchemy import func, select

from ..database import get_session
from ..models import LotteryStatus, Participant
from ..services.lottery_service import (
    add_participant,
    create_lottery,
    draw_winners,
    ensure_group,
    get_active_lottery,
)
from ..utils import format_winners, humanize_deadline, is_user_admin, parse_deadline

ASK_TITLE, ASK_DESCRIPTION, ASK_WINNERS, ASK_DEADLINE, ASK_STRATEGY, ASK_PRESET = range(6)


async def new_lottery_entry(update: Update, context: CallbackContext) -> int:
    message = update.effective_message
    if not message:
        return ConversationHandler.END

    if not await is_user_admin(update, context):
        await message.reply_text("只有群管理员可以发起抽奖。")
        return ConversationHandler.END

    chat = update.effective_chat
    if not chat:
        await message.reply_text("只能在群聊中使用该命令。")
        return ConversationHandler.END

    async with get_session() as session:
        active = await get_active_lottery(session, chat.id)
        if active:
            await message.reply_text("当前已有正在进行的抽奖，先完成后再创建新抽奖。")
            return ConversationHandler.END

    user = update.effective_user
    if not user:
        await message.reply_text("无法识别用户，请稍后再试。")
        return ConversationHandler.END

    context.user_data["new_lottery"] = {"chat_id": chat.id, "created_by": user.id}
    await message.reply_text("请输入抽奖标题：")
    return ASK_TITLE


async def ask_description(update: Update, context: CallbackContext) -> int:
    message = update.effective_message
    if not message:
        return ConversationHandler.END
    data = context.user_data.get("new_lottery", {})
    data["title"] = (message.text or "").strip()
    context.user_data["new_lottery"] = data
    await message.reply_text("请输入抽奖描述（可输入 skip 跳过）：")
    return ASK_DESCRIPTION


async def ask_winner_count(update: Update, context: CallbackContext) -> int:
    message = update.effective_message
    if not message:
        return ConversationHandler.END
    data = context.user_data.get("new_lottery", {})
    text = (message.text or "").strip()
    if text.lower() != "skip":
        data["description"] = text
    else:
        data["description"] = None
    context.user_data["new_lottery"] = data
    await message.reply_text("请输入中奖人数（数字）：")
    return ASK_WINNERS


async def ask_deadline(update: Update, context: CallbackContext) -> int:
    message = update.effective_message
    if not message:
        return ConversationHandler.END
    data = context.user_data.get("new_lottery", {})
    text = (message.text or "").strip()
    try:
        winners = int(text)
        if winners <= 0:
            raise ValueError
    except ValueError:
        await message.reply_text("请输入大于 0 的数字。请重新输入中奖人数：")
        return ASK_WINNERS
    data["winners_count"] = winners
    context.user_data["new_lottery"] = data
    await message.reply_text(
        "请输入报名截止时间：\n"
        "- 直接输入分钟数（例如 60 表示 60 分钟后截止）；\n"
        "- 或输入 ISO8601 时间（2024-06-01T12:00:00+08:00）；\n"
        "- 或输入 skip 保持无限期。"
    )
    return ASK_DEADLINE


async def ask_strategy(update: Update, context: CallbackContext) -> int:
    message = update.effective_message
    if not message:
        return ConversationHandler.END
    data = context.user_data.get("new_lottery", {})
    text = (message.text or "").strip()
    if text.lower() == "skip":
        deadline = None
    else:
        deadline = parse_deadline(text)
        if not deadline:
            await message.reply_text("无法解析时间，请重新输入（或输入 skip 跳过）：")
            return ASK_DEADLINE
    data["join_deadline"] = deadline
    context.user_data["new_lottery"] = data
    await message.reply_text("请输入抽奖策略：random（完全随机）或 preset（先满足预设中奖者）：")
    return ASK_STRATEGY


async def ask_preset(update: Update, context: CallbackContext) -> int:
    message = update.effective_message
    if not message:
        return ConversationHandler.END
    data = context.user_data.get("new_lottery", {})
    text = (message.text or "").strip().lower()
   if text not in {"random", "preset"}:
        await message.reply_text("请输入 random 或 preset：")
        return ASK_STRATEGY
    data["strategy"] = text
    context.user_data["new_lottery"] = data
    await message.reply_text(
        "如需指定中奖者，请输入用户ID列表，以逗号分隔；\n"
        "如果不知道用户ID，可让其私聊机器人并使用 /id 获取（后续可实现）；目前请输入数字ID；\n"
        "输入 skip 则不指定。"
    )
    return ASK_PRESET


async def finalize_lottery(update: Update, context: CallbackContext) -> int:
    message = update.effective_message
    if not message:
        return ConversationHandler.END
    data: Dict = context.user_data.get("new_lottery") or {}
    raw = (message.text or "").strip()
    preset_ids: List[int] = []
    if raw.lower() != "skip" and raw:
        try:
            preset_ids = [int(item.strip()) for item in raw.split(",") if item.strip()]
        except ValueError:
            await message.reply_text("预设中奖者列表必须是数字ID，请重新输入或 skip：")
            return ASK_PRESET

    chat_id = data.get("chat_id")
    created_by = data.get("created_by")
    if not chat_id or not created_by:
        await message.reply_text("上下文丢失，请重新开始 /newlottery。")
        return ConversationHandler.END

    async with get_session() as session:
        await ensure_group(session, chat_id, update.effective_chat.title if update.effective_chat else None)
        lottery = await create_lottery(
            session,
            chat_id=chat_id,
            created_by=created_by,
            title=data.get("title", "未命名"),
            description=data.get("description"),
            winners_count=data.get("winners_count", 1),
            join_deadline=data.get("join_deadline"),
            strategy=data.get("strategy", "random"),
            preset_user_ids=preset_ids,
        )
        await session.commit()

    context.user_data.pop("new_lottery", None)

    deadline_text = humanize_deadline(lottery.join_deadline)
    await message.reply_text(
        "抽奖创建成功！\n"
        f"标题：{lottery.title}\n"
        f"中奖人数：{lottery.winners_count}\n"
        f"截止：{deadline_text}\n"
        "大家可以使用 /join 报名。"
    )
    return ConversationHandler.END


async def cancel(update: Update, context: CallbackContext) -> int:
    message = update.effective_message
    if message:
        await message.reply_text("已取消当前操作。")
    context.user_data.pop("new_lottery", None)
    return ConversationHandler.END


async def join_lottery(update: Update, context: CallbackContext) -> None:
    message = update.effective_message
    if not message:
        return
    chat = update.effective_chat
    if not chat:
        await message.reply_text("请在群组中使用该命令。")
        return

    async with get_session() as session:
        lottery = await get_active_lottery(session, chat.id)
        if not lottery:
            await message.reply_text("当前没有可参与的抽奖。")
            return

        if lottery.join_deadline and datetime.now(timezone.utc) > lottery.join_deadline:
            lottery.status = LotteryStatus.CLOSED
            await session.commit()
            await message.reply_text("报名已截止。")
            return

        user = update.effective_user
        if not user:
            await message.reply_text("无法识别用户。")
            return
        participant = await add_participant(
            session,
            lottery=lottery,
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
        )
        await session.commit()

    await message.reply_text("报名成功！祝你好运～")


async def draw(update: Update, context: CallbackContext) -> None:
    message = update.effective_message
    if not message:
        return
    if not await is_user_admin(update, context):
        await message.reply_text("只有管理员可以开奖。")
        return

    chat = update.effective_chat
    if not chat:
        await message.reply_text("请在群组中使用该命令。")
        return

    async with get_session() as session:
        lottery = await get_active_lottery(session, chat.id)
        if not lottery:
            await message.reply_text("当前没有待开奖的抽奖。")
            return

        participants_count = await session.scalar(
            select(func.count(Participant.id)).where(Participant.lottery_id == lottery.id)
        )
        if not participants_count:
            await message.reply_text("还没有人参与，无法开奖。")
            return

        winners = await draw_winners(session, lottery=lottery)
        await session.commit()

    if not winners:
        await message.reply_text("还没有人参与，无法开奖。")
        return

    await message.reply_text("开奖啦！\n" + format_winners(winners))


async def status(update: Update, context: CallbackContext) -> None:
    message = update.effective_message
    if not message:
        return
    chat = update.effective_chat
    if not chat:
        await message.reply_text("请在群组中使用该命令。")
        return

    async with get_session() as session:
        lottery = await get_active_lottery(session, chat.id)
        if not lottery:
            await message.reply_text("当前没有进行中的抽奖。")
            return

        participants_count = await session.scalar(
            select(func.count(Participant.id)).where(Participant.lottery_id == lottery.id)
        )
        participants_count = participants_count or 0

    deadline_text = humanize_deadline(lottery.join_deadline)
    await message.reply_text(
        f"抽奖：{lottery.title}\n"
        f"状态：{lottery.status.value}\n"
        f"参与人数：{participants_count}\n"
        f"截止：{deadline_text}"
    )


def register_lottery_handlers(application: Application) -> None:
    conversation = ConversationHandler(
        entry_points=[CommandHandler("newlottery", new_lottery_entry)],
        states={
            ASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_description)],
            ASK_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_winner_count)],
            ASK_WINNERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_deadline)],
            ASK_DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_strategy)],
            ASK_STRATEGY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_preset)],
            ASK_PRESET: [MessageHandler(filters.TEXT & ~filters.COMMAND, finalize_lottery)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="lottery_setup",
        persistent=False,
    )

    application.add_handler(conversation)
    application.add_handler(CommandHandler("join", join_lottery))
    application.add_handler(CommandHandler("draw", draw))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("cancel", cancel))
