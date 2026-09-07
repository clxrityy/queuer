from __future__ import annotations

import asyncio
import logging

from .bot import QueuerBot, register_commands
from .config import load_config
from .db import initialize_database
from .logging import configure_logging


LOGGER = logging.getLogger(__name__)


async def run() -> int:
    configure_logging()
    config = load_config()

    await initialize_database(
        database_path=config.database_path,
        guild_id=config.guild_id,
        default_timezone=config.default_timezone,
    )

    bot = QueuerBot(config)
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
