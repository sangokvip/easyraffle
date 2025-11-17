from __future__ import annotations

import asyncio
import logging

from loguru import logger
from telegram.ext import Application

from .config import settings
from .database import init_db
from .handlers.basic import register_basic_handlers
from .handlers.lottery import register_lottery_handlers


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("Logging configured")


def build_application() -> Application:
    application = Application.builder().token(settings.telegram_bot_token).build()
    register_basic_handlers(application)
    register_lottery_handlers(application)
    return application


def run_webhook(application: Application) -> None:
    logger.info("Starting webhook mode at %s", settings.webhook_url)
    application.run_webhook(
        listen="0.0.0.0",
        port=8443,
        url_path="/telegram-webhook",
        webhook_url=settings.webhook_url,
        secret_token=settings.webhook_secret,
        drop_pending_updates=True,
    )


def run_polling(application: Application) -> None:
    logger.info("Starting polling mode")
    application.run_polling(drop_pending_updates=True)


def ensure_event_loop() -> None:
    """Prepare an event loop for PTB when running in sync context."""
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)


def main() -> None:
    configure_logging()
    asyncio.run(init_db())
    ensure_event_loop()
    application = build_application()
    if settings.webhook_url:
        run_webhook(application)
    else:
        run_polling(application)


if __name__ == "__main__":
    main()
