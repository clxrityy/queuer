from __future__ import annotations

import traceback

import discord
from discord import app_commands


def truncate_snippet(snippet: str, limit: int = 900) -> str:
    if len(snippet) > limit:
        return snippet[: limit - 3] + "..."
    return snippet


def build_snippet_embed(
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
        value=f"```{language}\n{truncate_snippet(snippet)}\n```",
        inline=False,
    )
    return embed


def build_error_embed(
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

    return build_snippet_embed(
        title=title,
        description=f"An error occurred while running `{command_name or 'unknown'}`.",
        snippet=snippet,
        language="text",
        color=discord.Color.red(),
    )


def format_log_snippet(error: app_commands.AppCommandError) -> str:
    if isinstance(error, app_commands.CommandInvokeError):
        return "".join(traceback.format_exception(error.original))
    return "".join(traceback.format_exception(error))