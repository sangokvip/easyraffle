from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return
    await message.reply_text(
        "欢迎使用抽奖机器人！\n"
        "将机器人设为群管理员后，使用 /newlottery 创建抽奖，/join 参与，/draw 开奖。"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return
    await message.reply_text(
        "指令列表:\n"
        "• /newlottery - 群管理员发起抽奖\n"
        "• /join - 报名当前抽奖\n"
        "• /draw - 管理员立即开奖\n"
        "• /status - 查看抽奖状态\n"
        "• /cancel - 在配置流程中取消"
    )


def register_basic_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
