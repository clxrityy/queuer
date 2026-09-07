from __future__ import annotations

import json
from dataclasses import asdict
from datetime import timedelta

from .models import DraftPayload, QuestionDraft, QueueItem, ServiceBundle, utcnow
from .repositories import (
    GuildSettingsRepository,
    QuestionDraftRepository,
    QueueRepository,
    RoleAssignmentRepository,
)


ROLE_PURPOSE_ADMIN = "admin"
ROLE_PURPOSE_CONTRIBUTOR = "contributor"
ROLE_PURPOSE_ELIGIBLE = "eligible"
ROLE_PURPOSE_ALERT = "alert"


class ConfigurationService:
    def __init__(
        self,
        settings_repository: GuildSettingsRepository,
        role_repository: RoleAssignmentRepository,
    ) -> None:
        self.settings_repository = settings_repository
        self.role_repository = role_repository

    async def get_snapshot(self, guild_id: int) -> dict[str, object]:
        settings = await self.settings_repository.get(guild_id)
        roles = await self.role_repository.list_for_guild(guild_id)
        roles_by_purpose: dict[str, list[int]] = {}
        for role in roles:
            roles_by_purpose.setdefault(role.purpose, []).append(role.role_id)

        return {
            "settings": asdict(settings) if settings is not None else None,
            "roles": roles_by_purpose,
        }

    async def set_qotd_channel(self, guild_id: int, channel_id: int) -> None:
        await self.settings_repository.update_qotd_channel(guild_id, channel_id)

    async def set_schedule(self, guild_id: int, schedule_time: str, timezone: str, enabled: bool) -> None:
        await self.settings_repository.update_schedule(
            guild_id,
            schedule_time=schedule_time,
            timezone=timezone,
            enabled=enabled,
        )

    async def set_reminder_interval(self, guild_id: int, interval_minutes: int | None) -> None:
        await self.settings_repository.update_reminder_interval(guild_id, interval_minutes)

    async def replace_admin_roles(self, guild_id: int, role_ids: list[int]) -> None:
        await self.role_repository.replace_for_purpose(guild_id, ROLE_PURPOSE_ADMIN, role_ids)

    async def replace_contributor_roles(self, guild_id: int, role_ids: list[int]) -> None:
        await self.role_repository.replace_for_purpose(guild_id, ROLE_PURPOSE_CONTRIBUTOR, role_ids)

    async def replace_eligible_roles(self, guild_id: int, role_ids: list[int]) -> None:
        await self.role_repository.replace_for_purpose(guild_id, ROLE_PURPOSE_ELIGIBLE, role_ids)

    async def replace_alert_roles(self, guild_id: int, role_ids: list[int]) -> None:
        await self.role_repository.replace_for_purpose(guild_id, ROLE_PURPOSE_ALERT, role_ids)


class DraftService:
    def __init__(self, draft_repository: QuestionDraftRepository) -> None:
        self.draft_repository = draft_repository

    async def begin_or_resume(self, guild_id: int, creator_user_id: int, *, ttl_minutes: int = 60) -> QuestionDraft:
        draft = await self.draft_repository.get_active_for_creator(guild_id, creator_user_id)
        if draft is not None:
            return draft

        expires_at = utcnow() + timedelta(minutes=ttl_minutes)
        payload = asdict(DraftPayload())
        return await self.draft_repository.create(
            guild_id,
            creator_user_id,
            current_step="question",
            status="draft",
            payload=payload,
            expires_at=expires_at,
        )

    async def save_progress(
        self,
        draft_id: int,
        *,
        current_step: str,
        payload_patch: dict[str, object],
        status: str = "draft",
        ttl_minutes: int = 60,
    ) -> QuestionDraft:
        draft = await self.draft_repository.get(draft_id)
        if draft is None:
            raise ValueError(f"Unknown draft id: {draft_id}")

        payload = json.loads(draft.payload_json)
        payload.update(payload_patch)
        expires_at = utcnow() + timedelta(minutes=ttl_minutes)
        await self.draft_repository.update(
            draft_id,
            current_step=current_step,
            status=status,
            payload=payload,
            expires_at=expires_at,
        )

        updated = await self.draft_repository.get(draft_id)
        if updated is None:
            raise RuntimeError("Draft update succeeded but the draft could not be reloaded")
        return updated

    async def mark_awaiting_confirmation(self, draft_id: int, *, ttl_minutes: int = 60) -> QuestionDraft:
        return await self.save_progress(
            draft_id,
            current_step="confirm",
            status="awaiting_confirmation",
            payload_patch={},
            ttl_minutes=ttl_minutes,
        )


class QueueService:
    def __init__(self, queue_repository: QueueRepository, draft_repository: QuestionDraftRepository) -> None:
        self.queue_repository = queue_repository
        self.draft_repository = draft_repository

    async def confirm_draft(self, draft_id: int, approving_user_id: int) -> QueueItem:
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

        queue_item = await self.queue_repository.create_from_draft(
            guild_id=draft.guild_id,
            draft_id=draft.id,
            creator_user_id=draft.creator_user_id,
            question_type=question_type,
            prompt_text=prompt_text,
            payload=payload,
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


def build_service_bundle(
    settings_repository: GuildSettingsRepository,
    role_repository: RoleAssignmentRepository,
    draft_repository: QuestionDraftRepository,
    queue_repository: QueueRepository,
) -> ServiceBundle:
    return ServiceBundle(
        configuration=ConfigurationService(settings_repository, role_repository),
        drafts=DraftService(draft_repository),
        queue=QueueService(queue_repository, draft_repository),
    )