from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


DATACLASS_KWARGS = {"slots": True} if sys.version_info >= (3, 10) else {}


@dataclass(**DATACLASS_KWARGS)
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


def _normalize_env_value(value: str) -> str:
    normalized = value.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"\"", "'"}:
        normalized = normalized[1:-1].strip()
    return normalized


def _getenv(name: str, default: str = "") -> str:
    return _normalize_env_value(os.getenv(name, default))


def _require(name: str) -> str:
    value = _getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def load_config() -> AppConfig:
    database_path = Path(_getenv("DATABASE_PATH", "data/queuer.sqlite3")).expanduser()
    return AppConfig(
        bot_token=_require("BOT_TOKEN"),
        bot_client_id=_require("BOT_CLIENT_ID"),
        bot_application_id=_require("BOT_APPLICATION_ID"),
        guild_id=int(_require("GUILD_ID")),
        env=_getenv("ENV", "development") or "development",
        database_path=database_path,
        default_timezone=_getenv("DEFAULT_TIMEZONE", "UTC") or "UTC",
    )
