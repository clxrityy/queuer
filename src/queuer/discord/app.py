from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import random
from typing import Optional

import discord
from discord.ext import commands, tasks

from ..config import AppConfig
from ..models import ServiceBundle
from .qotd_delivery import (
    build_queue_post_content,
    dedupe_preserving_order,
    get_cycle_candidate_member_ids,
)


LOGGER = logging.getLogger(__name__)
MANAGED_WEBHOOK_NAME = "Queuer QOTD"


@dataclass
class WebhookPersona:
    username: str
    avatar_url: Optional[str]
    selected_user_id: Optional[int] = None


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
        if not self.dispatch_scheduled_posts.is_running():
            self.dispatch_scheduled_posts.start()

    async def close(self) -> None:
        if self.dispatch_scheduled_posts.is_running():
            self.dispatch_scheduled_posts.cancel()
        await super().close()

    @tasks.loop(seconds=30)
    async def dispatch_scheduled_posts(self) -> None:
        try:
            await self._dispatch_due_queue_item()
        except Exception:
            LOGGER.exception("Scheduled QOTD dispatch failed")

    @dispatch_scheduled_posts.before_loop
    async def before_dispatch_scheduled_posts(self) -> None:
        await self.wait_until_ready()

    async def _dispatch_due_queue_item(self) -> None:
        settings = await self.services.configuration.get_settings(self.config.guild_id)
        queue_item = await self.services.queue.get_due_queue_item(
            self.config.guild_id,
            default_timezone=self.config.default_timezone,
        )
        if queue_item is None:
            return
        if settings is None or settings.qotd_channel_id is None:
            LOGGER.warning("Skipping queued QOTD #%s because no QOTD channel is configured", queue_item.id)
            return

        channel = self.get_channel(settings.qotd_channel_id)
        if channel is None:
            try:
                channel = await self.fetch_channel(settings.qotd_channel_id)
            except discord.DiscordException:
                LOGGER.exception("Unable to fetch configured QOTD channel %s", settings.qotd_channel_id)
                return

        if not isinstance(channel, discord.TextChannel):
            LOGGER.warning("Configured QOTD channel %s is not a text channel", settings.qotd_channel_id)
            return

        snapshot = await self.services.configuration.get_snapshot(self.config.guild_id)
        roles = snapshot.get("roles", {}) if isinstance(snapshot, dict) else {}
        alert_role_ids = [int(role_id) for role_id in roles.get("alert", [])]
        eligible_role_ids = [int(role_id) for role_id in roles.get("eligible", [])]

        payload = json.loads(queue_item.payload_json)
        content = build_queue_post_content(
            queue_item.prompt_text,
            payload,
            alert_role_ids=alert_role_ids,
        )
        persona = await self._resolve_webhook_persona(channel.guild, payload, eligible_role_ids=eligible_role_ids)
        try:
            webhook = await self._get_or_create_managed_webhook(channel)
            message = await webhook.send(
                content=content,
                username=persona.username,
                avatar_url=persona.avatar_url,
                allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False),
                wait=True,
            )
        except discord.DiscordException as exc:
            LOGGER.exception("Failed to send queued QOTD #%s", queue_item.id)
            await self.services.queue.record_send_failure(
                self.config.guild_id,
                queue_item.id,
                error_message=f"{exc.__class__.__name__}: {exc}",
            )
            return

        if persona.selected_user_id is not None:
            await self.services.queue.record_member_selection(
                self.config.guild_id,
                user_id=persona.selected_user_id,
                queue_item_id=queue_item.id,
            )

        reaction_error_message: Optional[str] = None
        try:
            await self._add_reaction_poll_emojis(message, payload)
        except discord.DiscordException as exc:
            LOGGER.exception("Failed to add reaction options for queued QOTD #%s", queue_item.id)
            reaction_error_message = f"{exc.__class__.__name__}: {exc}"

        await self.services.queue.mark_sent(
            self.config.guild_id,
            queue_item.id,
            sent_message_id=message.id,
            sent_channel_id=channel.id,
        )

        if reaction_error_message is not None:
            await self.services.queue.record_send_failure(
                self.config.guild_id,
                queue_item.id,
                error_message=reaction_error_message,
            )
        LOGGER.info("Sent queued QOTD #%s to channel %s", queue_item.id, channel.id)

    async def _get_or_create_managed_webhook(self, channel: discord.TextChannel) -> discord.Webhook:
        bot_user_id = self.user.id if self.user is not None else None
        for webhook in await channel.webhooks():
            if webhook.name != MANAGED_WEBHOOK_NAME:
                continue
            if webhook.user is None or webhook.user.id != bot_user_id:
                continue
            return webhook

        return await channel.create_webhook(
            name=MANAGED_WEBHOOK_NAME,
            reason="Managed QOTD delivery webhook",
        )

    async def _resolve_webhook_persona(
        self,
        guild: discord.Guild,
        payload: dict[str, object],
        *,
        eligible_role_ids: list[int],
    ) -> WebhookPersona:
        target_user_id = payload.get("target_user_id")
        if isinstance(target_user_id, int):
            target_member = await self._get_member(guild, target_user_id)
            if target_member is not None:
                return self._build_member_persona(target_member)

        eligible_member = await self._select_rotating_eligible_member(guild, eligible_role_ids)
        if eligible_member is not None:
            persona = self._build_member_persona(eligible_member)
            persona.selected_user_id = eligible_member.id
            return persona

        return WebhookPersona(
            username=self.config.webhook_identity.default_name,
            avatar_url=self.config.webhook_identity.default_avatar_url,
        )

    async def _get_member(self, guild: discord.Guild, user_id: int) -> Optional[discord.Member]:
        member = guild.get_member(user_id)
        if member is not None:
            return member

        try:
            return await guild.fetch_member(user_id)
        except discord.DiscordException:
            LOGGER.warning("Unable to resolve guild member %s for webhook persona", user_id)
            return None

    async def _select_rotating_eligible_member(
        self,
        guild: discord.Guild,
        eligible_role_ids: list[int],
    ) -> Optional[discord.Member]:
        eligible_members_by_id: dict[int, discord.Member] = {}
        for role_id in eligible_role_ids:
            role = guild.get_role(role_id)
            if role is None:
                continue
            for member in role.members:
                if member.bot:
                    continue
                eligible_members_by_id.setdefault(member.id, member)

        if not eligible_members_by_id:
            return None

        eligible_member_ids = sorted(eligible_members_by_id)
        recent_selected_user_ids = await self.services.queue.list_recent_member_selection_user_ids(
            self.config.guild_id,
            eligible_user_ids=eligible_member_ids,
        )
        candidate_member_ids = get_cycle_candidate_member_ids(
            eligible_member_ids,
            recent_selected_user_ids,
        )
        if not candidate_member_ids:
            return None

        selected_user_id = random.choice(candidate_member_ids)
        return eligible_members_by_id[selected_user_id]

    def _build_member_persona(self, member: discord.Member) -> WebhookPersona:
        return WebhookPersona(
            username=member.display_name,
            avatar_url=str(member.display_avatar.url),
        )

    async def _add_reaction_poll_emojis(
        self,
        message: discord.WebhookMessage,
        payload: dict[str, object],
    ) -> None:
        reaction_options = dedupe_preserving_order(
            str(option) for option in (payload.get("reaction_options") or [])
        )
        for reaction_option in reaction_options:
            await message.add_reaction(discord.PartialEmoji.from_str(reaction_option))