from __future__ import annotations

import logging

import discord
from discord import app_commands

from ..app import QueuerBot
from ..embeds import build_error_embed, format_log_snippet, is_expected_app_command_error


LOGGER = logging.getLogger(__name__)


def register_system_commands(bot: QueuerBot) -> None:
    @bot.tree.command(name="ping", description="Verify the bot is online.")
    async def ping(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("Queuer is online.", ephemeral=True)


def register_error_handler(bot: QueuerBot) -> None:
    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        command_name = interaction.command.qualified_name if interaction.command else None
        if is_expected_app_command_error(error):
            LOGGER.warning(
                "App command rejected for %s: %s",
                command_name or "unknown",
                str(error) or error.__class__.__name__,
            )
        else:
            LOGGER.error(
                "App command error for %s\n%s",
                command_name or "unknown",
                format_log_snippet(error),
            )

        embed = build_error_embed(command_name, error)
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        await interaction.response.send_message(embed=embed, ephemeral=True)
