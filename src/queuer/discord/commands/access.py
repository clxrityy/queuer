from __future__ import annotations

import discord
from discord import app_commands

from ..app import QueuerBot


ROLE_PURPOSE_CHOICES = [
    app_commands.Choice(name="Admin", value="admin"),
    app_commands.Choice(name="Contributor", value="contributor"),
    app_commands.Choice(name="Eligible Member Pool", value="eligible"),
    app_commands.Choice(name="Alert", value="alert"),
]


async def ensure_contributor_access(bot: QueuerBot, interaction: discord.Interaction) -> None:
    snapshot = await bot.services.configuration.get_snapshot(bot.config.guild_id)
    configured_role_ids = {
        int(role_id) for role_id in snapshot.get("roles", {}).get("contributor", [])
    }
    if not configured_role_ids:
        return

    member_roles = getattr(interaction.user, "roles", [])
    member_role_ids = {int(role.id) for role in member_roles}
    if configured_role_ids.isdisjoint(member_role_ids):
        raise app_commands.CheckFailure("You are not allowed to add QOTD questions.")


async def ensure_admin_access(bot: QueuerBot, interaction: discord.Interaction) -> None:
    snapshot = await bot.services.configuration.get_snapshot(bot.config.guild_id)
    configured_role_ids = {int(role_id) for role_id in snapshot.get("roles", {}).get("admin", [])}
    member = interaction.user
    member_roles = getattr(member, "roles", [])
    member_role_ids = {int(role.id) for role in member_roles}

    if configured_role_ids:
        if configured_role_ids.isdisjoint(member_role_ids):
            raise app_commands.CheckFailure("You are not allowed to manage QOTD configuration.")
        return

    guild_permissions = getattr(member, "guild_permissions", None)
    if guild_permissions is not None and (guild_permissions.administrator or guild_permissions.manage_guild):
        return

    raise app_commands.CheckFailure("Admin roles are not configured, so only server admins can manage QOTD configuration.")


def collect_role_ids(*roles: discord.Role | None) -> list[int]:
    unique_role_ids: list[int] = []
    for role in roles:
        if role is None or role.id in unique_role_ids:
            continue
        unique_role_ids.append(role.id)
    return unique_role_ids


async def replace_roles_for_purpose(bot: QueuerBot, guild_id: int, purpose: str, role_ids: list[int]) -> None:
    if purpose == "admin":
        await bot.services.configuration.replace_admin_roles(guild_id, role_ids)
    elif purpose == "contributor":
        await bot.services.configuration.replace_contributor_roles(guild_id, role_ids)
    elif purpose == "eligible":
        await bot.services.configuration.replace_eligible_roles(guild_id, role_ids)
    elif purpose == "alert":
        await bot.services.configuration.replace_alert_roles(guild_id, role_ids)
    else:
        raise app_commands.AppCommandError(f"Unsupported role purpose: {purpose}")
