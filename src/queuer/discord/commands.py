from __future__ import annotations

import json
import logging

import discord
from discord import app_commands

from .app import QueuerBot
from .embeds import build_error_embed, build_snippet_embed, format_log_snippet


LOGGER = logging.getLogger(__name__)


def register_commands(bot: QueuerBot) -> None:
    @bot.tree.command(name="ping", description="Verify the bot is online.")
    async def ping(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("Queuer is online.", ephemeral=True)

    @bot.tree.command(name="qotd-config", description="Open the QOTD admin configuration panel.")
    @app_commands.guild_only()
    async def qotd_config(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        snapshot = await bot.services.configuration.get_snapshot(bot.config.guild_id)
        embed = build_snippet_embed(
            title="QOTD Configuration Snapshot",
            description="Current persisted configuration for this bot instance.",
            snippet=json.dumps(snapshot, indent=2, sort_keys=True, default=str),
            language="json",
            color=discord.Color.blurple(),
        )
        await interaction.followup.send(
            embed=embed,
            ephemeral=True,
        )

    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        command_name = interaction.command.qualified_name if interaction.command else None
        LOGGER.exception(
            "App command error for %s\n%s",
            command_name or "unknown",
            format_log_snippet(error),
        )

        embed = build_error_embed(command_name, error)
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        await interaction.response.send_message(embed=embed, ephemeral=True)