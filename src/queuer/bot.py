from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from .config import AppConfig


LOGGER = logging.getLogger(__name__)


class QueuerBot(commands.Bot):
    def __init__(self, config: AppConfig) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.message_content = False

        super().__init__(command_prefix="!", intents=intents)
        self.config = config

    async def setup_hook(self) -> None:
        guild = discord.Object(id=self.config.guild_id)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        LOGGER.info("Synced %s application commands for guild %s", len(synced), self.config.guild_id)


def register_commands(bot: QueuerBot) -> None:
    @bot.tree.command(name="ping", description="Verify the bot is online.")
    async def ping(interaction: discord.Interaction) -> None:
        await interaction.response.send_message("online asf")

    @bot.tree.command(name="qotd-config", description="Open the QOTD admin configuration panel.")
    @app_commands.guild_only()
    async def qotd_config(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "Configuration UI scaffolding is in place. Admin setup commands and views are next.",
            ephemeral=True,
        )
