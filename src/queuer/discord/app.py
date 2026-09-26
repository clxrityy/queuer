from __future__ import annotations

import json
import logging

import discord
from discord.ext import commands, tasks

from ..config import AppConfig
from ..models import ServiceBundle
from .embeds import truncate_snippet


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

        payload = json.loads(queue_item.payload_json)
        content = self._build_queue_post_content(queue_item.prompt_text, payload)
        try:
            message = await channel.send(content)
        except discord.DiscordException as exc:
            LOGGER.exception("Failed to send queued QOTD #%s", queue_item.id)
            await self.services.queue.record_send_failure(
                self.config.guild_id,
                queue_item.id,
                error_message=f"{exc.__class__.__name__}: {exc}",
            )
            return

        await self.services.queue.mark_sent(
            self.config.guild_id,
            queue_item.id,
            sent_message_id=message.id,
            sent_channel_id=channel.id,
        )
        LOGGER.info("Sent queued QOTD #%s to channel %s", queue_item.id, channel.id)

    def _build_queue_post_content(self, prompt_text: str, payload: dict[str, object]) -> str:
        target_user_id = payload.get("target_user_id")
        title = "**QOTD**" if target_user_id is None else f"**QOTD for <@{target_user_id}>**"

        lines = [title, prompt_text]

        reaction_options = payload.get("reaction_options") or []
        if reaction_options:
            lines.append("Options:")
            lines.extend(f"- {option}" for option in reaction_options)

        this_or_that_options = payload.get("this_or_that_options") or []
        if this_or_that_options:
            lines.append("This or that:")
            lines.extend(f"- {option}" for option in this_or_that_options)

        return truncate_snippet("\n".join(str(line) for line in lines if line), limit=1900)