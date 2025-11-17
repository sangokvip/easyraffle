from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    telegram_bot_token: str
    database_url: str
    global_admin_ids: List[int]
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN env variable is required")

        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise RuntimeError("DATABASE_URL env variable is required")

        admin_ids_raw = os.getenv("GLOBAL_ADMIN_IDS", "")
        admin_ids = []
        for item in admin_ids_raw.split(","):
            item = item.strip()
            if not item:
                continue
            try:
                admin_ids.append(int(item))
            except ValueError:
                raise RuntimeError("GLOBAL_ADMIN_IDS must contain integers") from None

        webhook_url = os.getenv("WEBHOOK_URL") or None
        webhook_secret = os.getenv("WEBHOOK_SECRET") or None

        return cls(
            telegram_bot_token=token,
            database_url=db_url,
            global_admin_ids=admin_ids,
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
        )


settings = Settings.from_env()
