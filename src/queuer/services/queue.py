from __future__ import annotations

import json

from ..models import QueueItem, utcnow
from ..repositories import QuestionDraftRepository, QueueRepository


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