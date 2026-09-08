from __future__ import annotations

import asyncio
import logging

from .config import load_config
from .db import Database
from .discord import QueuerBot, register_commands
from .logging import configure_logging
from .repositories import (
    GuildSettingsRepository,
    QuestionDraftRepository,
    QueueRepository,
    RoleAssignmentRepository,
)
from .services import build_service_bundle


LOGGER = logging.getLogger(__name__)


async def run() -> int:
    configure_logging()
    config = load_config()

    database = Database(config.database_path)
    await database.initialize(guild_id=config.guild_id, default_timezone=config.default_timezone)

    services = build_service_bundle(
        settings_repository=GuildSettingsRepository(database),
        role_repository=RoleAssignmentRepository(database),
        draft_repository=QuestionDraftRepository(database),
        queue_repository=QueueRepository(database),
    )

    bot = QueuerBot(config, services)
    register_commands(bot)

    LOGGER.info("Starting Queuer for guild %s", config.guild_id)
    async with bot:
        await bot.start(config.bot_token)
    return 0


def main() -> int:
    try:
        return asyncio.run(run())
    except KeyboardInterrupt:
        return 0
