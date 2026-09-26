from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from ..models import QueueItem, utcnow
from ..repositories import GuildSettingsRepository, QuestionDraftRepository, QueueRepository
from ..scheduling import is_daily_schedule_due, parse_schedule_override, parse_utc_timestamp


class QueueService:
    def __init__(
        self,
        queue_repository: QueueRepository,
        draft_repository: QuestionDraftRepository,
        settings_repository: GuildSettingsRepository,
    ) -> None:
        self.queue_repository = queue_repository
        self.draft_repository = draft_repository
        self.settings_repository = settings_repository

    async def confirm_draft(
        self,
        draft_id: int,
        approving_user_id: int,
        *,
        schedule_date: Optional[str] = None,
        schedule_time: Optional[str] = None,
        timezone_name: Optional[str] = None,
        default_timezone: str = "UTC",
    ) -> QueueItem:
        draft = await self.draft_repository.get(draft_id)
        if draft is None:
            raise ValueError(f"Unknown draft id: {draft_id}")

        payload = json.loads(draft.payload_json)
        prompt_text = str(payload.get("prompt_text") or "").strip()
        question_type = str(payload.get("question_type") or "").strip()
        if not prompt_text:
            raise ValueError("Draft is missing prompt_text")
        if not question_type:
            raise ValueError("Draft is missing question_type")

        settings = await self.settings_repository.get(draft.guild_id)
        effective_timezone = timezone_name or (settings.timezone if settings is not None else None) or default_timezone
        scheduled_for = parse_schedule_override(
            schedule_date,
            schedule_time,
            effective_timezone,
        )
        payload["scheduled_for"] = scheduled_for.isoformat().replace("+00:00", "Z") if scheduled_for is not None else None

        queue_item = await self.queue_repository.create_from_draft(
            guild_id=draft.guild_id,
            draft_id=draft.id,
            creator_user_id=draft.creator_user_id,
            question_type=question_type,
            prompt_text=prompt_text,
            payload=payload,
            scheduled_for=scheduled_for,
            target_user_id=payload.get("target_user_id"),
            approved_by_user_id=approving_user_id,
        )
        await self.draft_repository.update(
            draft.id,
            current_step="confirmed",
            status="confirmed",
            payload=payload,
            expires_at=utcnow(),
        )
        return queue_item

    async def list_queued(self, guild_id: int) -> list[QueueItem]:
        return await self.queue_repository.list_for_guild(guild_id, status="queued")

    async def remove_queued_item(self, guild_id: int, queue_item_id: int) -> QueueItem:
        queue_item = await self.queue_repository.get(queue_item_id)
        if queue_item is None or queue_item.guild_id != guild_id:
            raise ValueError(f"Unknown queue item id: {queue_item_id}")
        if queue_item.status != "queued":
            raise ValueError(f"Queue item #{queue_item_id} is no longer queued.")

        deleted = await self.queue_repository.delete_queued_item(guild_id, queue_item_id)
        if not deleted:
            raise ValueError(f"Queue item #{queue_item_id} is no longer queued.")
        return queue_item

    async def get_due_queue_item(self, guild_id: int, *, default_timezone: str) -> Optional[QueueItem]:
        queued_items = await self.queue_repository.list_for_guild(guild_id, status="queued")
        if not queued_items:
            return None

        now = datetime.now(timezone.utc)
        for queue_item in queued_items:
            if queue_item.scheduled_for is None:
                continue
            if parse_utc_timestamp(queue_item.scheduled_for) <= now:
                return queue_item

        queue_item = queued_items[0]
        if queue_item.scheduled_for is not None:
            return None

        settings = await self.settings_repository.get(guild_id)
        if settings is None or not settings.schedule_enabled or not settings.schedule_time:
            return None

        latest_sent_raw = await self.queue_repository.get_latest_successful_send(guild_id)
        latest_sent = parse_utc_timestamp(latest_sent_raw) if latest_sent_raw is not None else None
        timezone_name = settings.timezone or default_timezone
        if is_daily_schedule_due(now, settings.schedule_time, timezone_name, last_sent_at=latest_sent):
            return queue_item
        return None

    async def mark_sent(self, guild_id: int, queue_item_id: int, *, sent_message_id: int, sent_channel_id: int) -> None:
        sent_at = datetime.now(timezone.utc)
        await self.queue_repository.mark_sent(queue_item_id)
        await self.queue_repository.record_send_event(
            guild_id,
            queue_item_id=queue_item_id,
            status="sent",
            sent_message_id=sent_message_id,
            sent_channel_id=sent_channel_id,
            sent_at=sent_at,
        )

    async def record_send_failure(self, guild_id: int, queue_item_id: int, *, error_message: str) -> None:
        await self.queue_repository.record_send_event(
            guild_id,
            queue_item_id=queue_item_id,
            status="failed",
            error_message=error_message,
        )

    async def list_recent_member_selection_user_ids(self, guild_id: int, *, eligible_user_ids: list[int]) -> list[int]:
        return await self.queue_repository.list_recent_member_selection_user_ids(
            guild_id,
            eligible_user_ids=eligible_user_ids,
        )

    async def record_member_selection(self, guild_id: int, *, user_id: int, queue_item_id: int) -> None:
        await self.queue_repository.record_member_selection(
            guild_id,
            user_id=user_id,
            queue_item_id=queue_item_id,
        )

    async def edit_requires_reconfirmation(
        self,
        queue_item_id: int,
        *,
        payload_patch: dict[str, object],
    ) -> QueueItem:
        queue_item = await self.queue_repository.get(queue_item_id)
        if queue_item is None:
            raise ValueError(f"Unknown queue item id: {queue_item_id}")

        payload = json.loads(queue_item.payload_json)
        payload.update(payload_patch)
        prompt_text = str(payload.get("prompt_text") or queue_item.prompt_text)
        await self.queue_repository.mark_pending_reconfirmation(queue_item_id, payload, prompt_text)

        updated = await self.queue_repository.get(queue_item_id)
        if updated is None:
            raise RuntimeError("Queue item update succeeded but the item could not be reloaded")
        return updated