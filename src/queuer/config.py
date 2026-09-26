from __future__ import annotations

import configparser
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


DATACLASS_KWARGS = {"slots": True} if sys.version_info >= (3, 10) else {}


@dataclass(**DATACLASS_KWARGS)
class WebhookIdentityConfig:
    default_name: str
    default_avatar_url: Optional[str]


@dataclass(**DATACLASS_KWARGS)
class AppConfig:
    bot_token: str
    bot_client_id: str
    bot_application_id: str
    guild_id: int
    env: str
    database_path: Path
    default_timezone: str
    webhook_identity: WebhookIdentityConfig

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


def load_webhook_identity_config(config_path: Path) -> WebhookIdentityConfig:
    parser = configparser.ConfigParser()
    if config_path.exists():
        parser.read(config_path, encoding="utf-8")

    section = parser["webhook"] if parser.has_section("webhook") else {}
    default_name = _normalize_env_value(str(section.get("default_name", "QOTD"))).strip() or "QOTD"
    default_avatar_url = _normalize_env_value(str(section.get("default_avatar_url", ""))).strip() or None
    return WebhookIdentityConfig(
        default_name=default_name,
        default_avatar_url=default_avatar_url,
    )


def load_config() -> AppConfig:
    database_path = Path(_getenv("DATABASE_PATH", "data/queuer.sqlite3")).expanduser()
    webhook_config_path = Path(_getenv("WEBHOOK_CONFIG_PATH", "config/webhook.conf")).expanduser()
    return AppConfig(
        bot_token=_require("BOT_TOKEN"),
        bot_client_id=_require("BOT_CLIENT_ID"),
        bot_application_id=_require("BOT_APPLICATION_ID"),
        guild_id=int(_require("GUILD_ID")),
        env=_getenv("ENV", "development") or "development",
        database_path=database_path,
        default_timezone=_getenv("DEFAULT_TIMEZONE", "UTC") or "UTC",
        webhook_identity=load_webhook_identity_config(webhook_config_path),
    )
