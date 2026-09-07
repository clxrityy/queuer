from __future__ import annotations

import json
import logging
import traceback

import discord
from discord import app_commands
from discord.ext import commands

from .config import AppConfig
from .models import ServiceBundle


LOGGER = logging.getLogger(__name__)


def _truncate_snippet(snippet: str, limit: int = 900) -> str:
    if len(snippet) > limit:
        return snippet[: limit - 3] + "..."
    return snippet


def _build_snippet_embed(
    *,
    title: str,
    description: str,
    snippet: str,
    language: str = "text",
    color: discord.Color,
) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
    )
    embed.add_field(
        name="Snippet",
        value=f"```{language}\n{_truncate_snippet(snippet)}\n```",
        inline=False,
    )
    return embed


def _build_error_embed(
    command_name: str | None,
    error: app_commands.AppCommandError,
) -> discord.Embed:
    title = "Command Error"
    snippet = str(error) or error.__class__.__name__

    if isinstance(error, app_commands.CommandOnCooldown):
        title = "Command On Cooldown"
        snippet = f"Try again in {error.retry_after:.1f} seconds."
    elif isinstance(error, app_commands.MissingPermissions):
        title = "Missing Permissions"
        snippet = "You do not have the permissions required to use this command."
    elif isinstance(error, app_commands.BotMissingPermissions):
        title = "Bot Missing Permissions"
        snippet = "The bot is missing one or more permissions required to complete this action."
    elif isinstance(error, app_commands.CheckFailure):
        title = "Command Not Allowed"
        snippet = str(error) or "You cannot use this command here."
    elif isinstance(error, app_commands.CommandInvokeError):
        original = error.original
        title = f"{original.__class__.__name__}"
        snippet = str(original) or "The command raised an unexpected runtime error."
    elif isinstance(error, app_commands.TransformerError):
        title = "Invalid Input"
        snippet = str(error) or "One or more command values could not be parsed."

    return _build_snippet_embed(
        title=title,
        description=f"An error occurred while running `{command_name or 'unknown'}`.",
        snippet=snippet,
        language="text",
        color=discord.Color.red(),
    )


def _format_log_snippet(error: app_commands.AppCommandError) -> str:
    if isinstance(error, app_commands.CommandInvokeError):
        return "".join(traceback.format_exception(error.original))
    return "".join(traceback.format_exception(error))


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
        embed = _build_snippet_embed(
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
            _format_log_snippet(error),
        )

        embed = _build_error_embed(command_name, error)
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        await interaction.response.send_message(embed=embed, ephemeral=True)
