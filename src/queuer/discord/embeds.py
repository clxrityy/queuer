from __future__ import annotations

import traceback
from typing import Optional

import discord
from discord import app_commands


def is_expected_app_command_error(error: app_commands.AppCommandError) -> bool:
    return type(error) is app_commands.AppCommandError or isinstance(
        error,
        (
            app_commands.CommandOnCooldown,
            app_commands.MissingPermissions,
            app_commands.BotMissingPermissions,
            app_commands.CheckFailure,
            app_commands.TransformerError,
        ),
    )


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
    render_as_code_block: bool = True,
    field_name: str = "Snippet",
) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
    )
    field_value = (
        f"```{language}\n{truncate_snippet(snippet)}\n```"
        if render_as_code_block
        else truncate_snippet(snippet)
    )
    embed.add_field(
        name=field_name,
        value=field_value,
        inline=False,
    )
    return embed


def build_error_embed(
    command_name: Optional[str],
    error: app_commands.AppCommandError,
) -> discord.Embed:
    title = "Command Error"
    snippet = "The command could not be completed. Please try again later."

    if isinstance(error, app_commands.CommandOnCooldown):
        title = "Command On Cooldown"
        snippet = f"Try again in {error.retry_after:.1f} seconds."
    elif type(error) is app_commands.AppCommandError:
        title = "Invalid Input"
        snippet = str(error) or "One or more command values were invalid."
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
        snippet = "The command raised an unexpected runtime error."
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
        original = error.original
        return "".join(
            traceback.format_exception(type(original), original, original.__traceback__)
        )
    return "".join(traceback.format_exception(type(error), error, error.__traceback__))
