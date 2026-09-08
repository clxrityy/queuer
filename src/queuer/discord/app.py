from __future__ import annotations

import logging

import discord
from discord.ext import commands

from ..config import AppConfig
from ..models import ServiceBundle


LOGGER = logging.getLogger(__name__)


class QueuerBot(commands.Bot):
    def __init__(self, config: AppConfig, services: ServiceBundle) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.message_content = False

        super().__init__(command_prefix="!", intents=intents)
        self.config = config
        self.services = services

    async def setup_hook(self) -> None:
        guild = discord.Object(id=self.config.guild_id)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        LOGGER.info("Synced %s application commands for guild %s", len(synced), self.config.guild_id)