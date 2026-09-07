from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(slots=True)
class AppConfig:
    bot_token: str
    bot_client_id: str
    bot_application_id: str
    guild_id: int
    env: str
    database_path: Path
    default_timezone: str

    @property
    def is_development(self) -> bool:
        return self.env.lower() == "development"


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def load_config() -> AppConfig:
    database_path = Path(os.getenv("DATABASE_PATH", "data/queuer.sqlite3")).expanduser()
    return AppConfig(
        bot_token=_require("BOT_TOKEN"),
        bot_client_id=_require("BOT_CLIENT_ID"),
        bot_application_id=_require("BOT_APPLICATION_ID"),
        guild_id=int(_require("GUILD_ID")),
        env=os.getenv("ENV", "development").strip() or "development",
        database_path=database_path,
        default_timezone=os.getenv("DEFAULT_TIMEZONE", "UTC").strip() or "UTC",
    )
