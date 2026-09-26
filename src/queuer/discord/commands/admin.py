from __future__ import annotations

import json
from typing import Optional

import discord
from discord import app_commands

from ...scheduling import format_utc_for_display
from ..app import QueuerBot
from ..embeds import build_snippet_embed
from ..views import RoleSelectionView
from .access import ROLE_PURPOSE_CHOICES, ensure_admin_access


def _truncate_inline(value: str, limit: int = 60) -> str:
    cleaned = value.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def _format_queue_item_line(
    position: int,
    *,
    queue_item,
    timezone_name: str,
) -> str:
    if queue_item.scheduled_for is not None:
        schedule_label = format_utc_for_display(queue_item.scheduled_for, timezone_name)
    else:
        schedule_label = "default schedule"
    prompt = _truncate_inline(queue_item.prompt_text)
    return f"{position}. #{queue_item.id} • {queue_item.type} • {schedule_label} • {prompt}"


def _format_removed_queue_item_details(queue_item, *, timezone_name: str) -> str:
    lines = [
        f"Removed queued QOTD #{queue_item.id}.",
        f"Type: {queue_item.type}",
        f"Prompt: {_truncate_inline(queue_item.prompt_text, limit=120)}",
    ]
    if queue_item.scheduled_for is not None:
        lines.append(f"Schedule override: {format_utc_for_display(queue_item.scheduled_for, timezone_name)}")
    else:
        lines.append("Schedule: default daily schedule")
    return "\n".join(lines)


def register_admin_commands(bot: QueuerBot) -> None:
    @bot.tree.command(name="qotd-config", description="Open the QOTD admin configuration panel.")
    @app_commands.guild_only()
    async def qotd_config(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await ensure_admin_access(bot, interaction)
        snapshot = await bot.services.configuration.get_snapshot(bot.config.guild_id)
        embed = build_snippet_embed(
            title="QOTD Configuration Snapshot",
            description="Current persisted configuration for this bot instance.",
            snippet=json.dumps(snapshot, indent=2, sort_keys=True, default=str),
            language="json",
            color=discord.Color.blurple(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @bot.tree.command(name="qotd-set-channel", description="Set or clear the channel used for QOTD posts.")
    @app_commands.guild_only()
    @app_commands.describe(channel="Leave empty to clear the configured QOTD channel.")
    async def qotd_set_channel(
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        await ensure_admin_access(bot, interaction)

        await bot.services.configuration.set_qotd_channel(
            bot.config.guild_id,
            channel.id if channel is not None else None,
        )

        summary = f"QOTD channel set to {channel.mention}." if channel is not None else "QOTD channel cleared."
        embed = build_snippet_embed(
            title="QOTD Channel Updated",
            description="The delivery channel configuration was updated.",
            snippet=summary,
            language="text",
            color=discord.Color.blurple(),
            render_as_code_block=False,
            field_name="Details",
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @bot.tree.command(name="qotd-set-schedule", description="Set the default daily QOTD posting schedule.")
    @app_commands.guild_only()
    @app_commands.describe(
        time="Daily post time in HH:MM 24-hour format.",
        timezone="IANA timezone like UTC or America/New_York. Leave empty to reuse the current one.",
    )
    async def qotd_set_schedule(
        interaction: discord.Interaction,
        time: str,
        timezone: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        await ensure_admin_access(bot, interaction)

        settings = await bot.services.configuration.get_settings(bot.config.guild_id)
        effective_timezone = timezone or (settings.timezone if settings is not None else None) or bot.config.default_timezone
        try:
            await bot.services.configuration.set_schedule(
                bot.config.guild_id,
                time,
                effective_timezone,
                True,
            )
        except ValueError as exc:
            raise app_commands.AppCommandError(str(exc)) from exc

        embed = build_snippet_embed(
            title="QOTD Schedule Updated",
            description="The default daily posting schedule is now enabled.",
            snippet=f"Daily schedule: {time} {effective_timezone}",
            language="text",
            color=discord.Color.blurple(),
            render_as_code_block=False,
            field_name="Details",
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @bot.tree.command(name="qotd-disable-schedule", description="Disable the default daily QOTD posting schedule.")
    @app_commands.guild_only()
    async def qotd_disable_schedule(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await ensure_admin_access(bot, interaction)

        try:
            await bot.services.configuration.disable_schedule(bot.config.guild_id)
        except ValueError as exc:
            raise app_commands.AppCommandError(str(exc)) from exc
        embed = build_snippet_embed(
            title="QOTD Schedule Disabled",
            description="The default daily posting schedule was disabled.",
            snippet="Per-question schedule overrides will still be honored for queued items.",
            language="text",
            color=discord.Color.blurple(),
            render_as_code_block=False,
            field_name="Details",
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @bot.tree.command(name="qotd-queue", description="Show the currently queued QOTD items.")
    @app_commands.guild_only()
    async def qotd_queue(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await ensure_admin_access(bot, interaction)

        queued_items = await bot.services.queue.list_queued(bot.config.guild_id)
        if not queued_items:
            embed = build_snippet_embed(
                title="Queued QOTDs",
                description="There are no queued questions right now.",
                snippet="Queue is empty.",
                language="text",
                color=discord.Color.blurple(),
                render_as_code_block=False,
                field_name="Details",
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        settings = await bot.services.configuration.get_settings(bot.config.guild_id)
        timezone_name = (settings.timezone if settings is not None else None) or bot.config.default_timezone
        lines = [
            _format_queue_item_line(index, queue_item=queue_item, timezone_name=timezone_name)
            for index, queue_item in enumerate(queued_items, start=1)
        ]
        embed = build_snippet_embed(
            title="Queued QOTDs",
            description="Use `/qotd-remove queue_item_id:<id>` to remove a queued question.",
            snippet="\n".join(lines),
            language="text",
            color=discord.Color.blurple(),
            render_as_code_block=False,
            field_name="Queue",
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @bot.tree.command(name="qotd-remove", description="Remove a queued QOTD item by ID.")
    @app_commands.guild_only()
    @app_commands.describe(queue_item_id="The queued QOTD ID to remove. Use `/qotd-queue` to find it.")
    async def qotd_remove(interaction: discord.Interaction, queue_item_id: int) -> None:
        await interaction.response.defer(ephemeral=True)
        await ensure_admin_access(bot, interaction)

        settings = await bot.services.configuration.get_settings(bot.config.guild_id)
        timezone_name = (settings.timezone if settings is not None else None) or bot.config.default_timezone
        try:
            removed_item = await bot.services.queue.remove_queued_item(bot.config.guild_id, queue_item_id)
        except ValueError as exc:
            raise app_commands.AppCommandError(str(exc)) from exc

        embed = build_snippet_embed(
            title="Queued QOTD Removed",
            description="The queued question was removed successfully.",
            snippet=_format_removed_queue_item_details(removed_item, timezone_name=timezone_name),
            language="text",
            color=discord.Color.green(),
            render_as_code_block=False,
            field_name="Details",
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @bot.tree.command(name="qotd-set-roles", description="Open an interactive role picker for a QOTD role group.")
    @app_commands.guild_only()
    @app_commands.describe(purpose="Which QOTD role group to update.")
    @app_commands.choices(purpose=ROLE_PURPOSE_CHOICES)
    async def qotd_set_roles(
        interaction: discord.Interaction,
        purpose: app_commands.Choice[str],
    ) -> None:
        await ensure_admin_access(bot, interaction)
        snapshot = await bot.services.configuration.get_snapshot(bot.config.guild_id)
        configured_role_ids = [int(role_id) for role_id in snapshot.get("roles", {}).get(purpose.value, [])]
        guild = interaction.guild
        if guild is None:
            raise app_commands.AppCommandError("This command can only be used inside a server.")

        available_roles = [
            role
            for role in reversed(guild.roles)
            if not role.is_default() and not role.managed
        ]
        if not available_roles:
            raise app_commands.AppCommandError("This server does not have any selectable roles.")

        view = RoleSelectionView(
            bot=bot,
            owner_user_id=interaction.user.id,
            purpose=purpose.value,
            available_roles=available_roles,
            current_role_ids=set(configured_role_ids),
        )
        await interaction.response.send_message(
            embed=view.build_embed(f"Pick roles for the `{purpose.value}` group."),
            view=view,
            ephemeral=True,
        )
        view.message = await interaction.original_response()

